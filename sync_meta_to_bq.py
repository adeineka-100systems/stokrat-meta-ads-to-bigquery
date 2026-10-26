from datetime import datetime, timedelta
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adsinsights import AdsInsights
from google.cloud import bigquery
import os

# Налаштування credentials для BigQuery
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
DATASET_ID = os.environ.get("GCP_DATASET_ID")
TABLE_ID = "meta_ads_insights"

# Налаштування Meta API
APP_ID = os.environ.get("META_APP_ID")
APP_SECRET = os.environ.get("META_APP_SECRET")
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID")  # формат: act_XXXXXXXXX

FacebookAdsApi.init(app_id=APP_ID, app_secret=APP_SECRET, access_token=ACCESS_TOKEN)

def fetch_meta_insights():
    account = AdAccount(AD_ACCOUNT_ID)
    
    params = {
        'level': 'ad',  # розбивка до рівня конкретного оголошення (Ad Name)
        'time_increment': 1,
        'date_preset': 'yesterday', 
    }

    fields = [
        AdsInsights.Field.date_start,
        AdsInsights.Field.campaign_id,
        AdsInsights.Field.campaign_name,
        AdsInsights.Field.adset_id,
        AdsInsights.Field.adset_name,
        AdsInsights.Field.ad_id,
        AdsInsights.Field.ad_name,
        AdsInsights.Field.spend,
        AdsInsights.Field.impressions,
        AdsInsights.Field.clicks,
        AdsInsights.Field.actions,      
        AdsInsights.Field.action_values 
    ]

    insights = account.get_insights(fields=fields, params=params)
    rows_to_insert = []
    
    for insight in insights:
        actions = insight.get('actions', [])
        purchases = 0
        leads = 0
        for action in actions:
            action_type = action.get('action_type', '')
            if 'purchase' in action_type:
                purchases += int(float(action.get('value', 0)))
            elif 'lead' in action_type:
                leads += int(float(action.get('value', 0)))

        action_values = insight.get('action_values', [])
        purchase_value = 0.0
        for val in action_values:
            if 'purchase' in val.get('action_type', ''):
                purchase_value += float(val.get('value', 0.0))

        row = {
            "date": insight.get('date_start'),
            "campaign_id": str(insight.get('campaign_id')),
            "campaign_name": str(insight.get('campaign_name')),
            "adset_id": str(insight.get('adset_id')),
            "adset_name": str(insight.get('adset_name')),
            "ad_id": str(insight.get('ad_id')),
            "ad_name": str(insight.get('ad_name', '')),
            "spend": float(insight.get('spend', 0.0)),
            "impressions": int(insight.get('impressions', 0)),
            "clicks": int(insight.get('clicks', 0)),
            "purchases": purchases,
            "purchase_value": purchase_value,
            "leads": leads
        }
        rows_to_insert.append(row)

    return rows_to_insert

def insert_to_bigquery(data):
    if not data:
        print("Немає даних для завантаження за вчора.")
        return

    client = bigquery.Client()
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    
    # Визначаємо схему таблиці
    schema = [
        bigquery.SchemaField("date", "DATE"),
        bigquery.SchemaField("campaign_id", "STRING"),
        bigquery.SchemaField("campaign_name", "STRING"),
        bigquery.SchemaField("adset_id", "STRING"),
        bigquery.SchemaField("adset_name", "STRING"),
        bigquery.SchemaField("ad_id", "STRING"),
        bigquery.SchemaField("ad_name", "STRING"),
        bigquery.SchemaField("spend", "FLOAT"),
        bigquery.SchemaField("impressions", "INTEGER"),
        bigquery.SchemaField("clicks", "INTEGER"),
        bigquery.SchemaField("purchases", "INTEGER"),
        bigquery.SchemaField("purchase_value", "FLOAT"),
        bigquery.SchemaField("leads", "INTEGER"),
    ]

    # Створюємо таблицю, якщо вона ще не існує
    table = bigquery.Table(table_ref, schema=schema)
    table = client.create_table(table, exists_ok=True)
    print(f"Таблиця {table.project}.{table.dataset_id}.{table.table_id} перевірена/створена успішно.")

    errors = client.insert_rows_json(table_ref, data)
    if errors == []:
        print(f"Успішно завантажено {len(data)} рядків у BigQuery!")
    else:
        print(f"Помилки при вставці в BigQuery: {errors}")

if __name__ == "__main__":
    data = fetch_meta_insights()
    insert_to_bigquery(data)

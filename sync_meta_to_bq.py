from datetime import datetime, timedelta
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adsinsights import AdsInsights
from google.cloud import bigquery
import os

# Налаштування credentials для BigQuery
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
DATASET_ID = os.environ.get("GCP_DATASET_ID")

# Налаштування Meta API
APP_ID = os.environ.get("META_APP_ID")
APP_SECRET = os.environ.get("META_APP_SECRET")
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")

# Словник кабінетів та відповідних їм таблиць у BigQuery
ACCOUNTS_CONFIG = {
    "buyers": {
        "account_id": os.environ.get("META_AD_ACCOUNT_ID"),
        "table_id": "meta_ads_insights_buyers"
    },
    "sellers": {
        "account_id": os.environ.get("META_AD_ACCOUNT_ID_SELLERS"),
        "table_id": "meta_ads_insights_sellers"
    }
}

FacebookAdsApi.init(app_id=APP_ID, app_secret=APP_SECRET, access_token=ACCESS_TOKEN)

def fetch_meta_insights(account_id):
    if not account_id:
        print(f"Пропускаємо кабінет: ID не задано.")
        return []
        
    account = AdAccount(account_id)
    
    params = {
        'level': 'ad',  # розбивка до рівня конкретного оголошення
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

    try:
        insights = account.get_insights(fields=fields, params=params)
    except Exception as e:
        print(f"Помилка при отриманні даних для кабінету {account_id}: {e}")
        return []
        
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

def insert_to_bigquery(data, table_id):
    if not data:
        print(f"Немає даних для завантаження в таблицю {table_id} за вчора.")
        return

    client = bigquery.Client()
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_id}"
    
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

    table = bigquery.Table(table_ref, schema=schema)
    table = client.create_table(table, exists_ok=True)
    print(f"Таблиця {table.project}.{table.dataset_id}.{table.table_id} перевірена/створена.")

    errors = client.insert_rows_json(table_ref, data)
    if errors == []:
        print(f"Успішно завантажено {len(data)} рядків у таблицю {table_id}!")
    else:
        print(f"Помилки при вставці в BigQuery для {table_id}: {errors}")

if __name__ == "__main__":
    for key, config in ACCOUNTS_CONFIG.items():
        print(f"Обробка кабінету ({key}): {config['account_id']}")
        data = fetch_meta_insights(config['account_id'])
        insert_to_bigquery(data, config['table_id'])

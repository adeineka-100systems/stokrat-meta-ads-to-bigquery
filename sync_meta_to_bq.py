import os
import datetime
from google.cloud import bigquery
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

# Налаштування доступу
APP_SECRET = os.environ.get("META_APP_SECRET")
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")

PROJECT_ID = "budmo-463809"
DATASET_ID = "stokrat_meta_ads"  # ваш основний датасет

# Список кабінетів та їх цільових таблиць
ACCOUNTS = {
    "buyers": {
        "ad_account_id": os.environ.get("META_AD_ACCOUNT_ID"),
        "table_id": "meta_ads_insights_buyers"
    },
    "sellers": {
        "ad_account_id": os.environ.get("META_AD_ACCOUNT_ID_SELLERS"),
        "table_id": "meta_ads_insights_sellers"
    }
}

print("Ініціалізація Meta API...")
FacebookAdsApi.init(access_token=ACCESS_TOKEN, app_secret=APP_SECRET)

end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=90)

date_preset_params = {
    'time_range': {
        'since': start_date.strftime('%Y-%m-%d'),
        'until': end_date.strftime('%Y-%m-%d')
    },
    'time_increment': 1,
    'level': 'campaign'
}

fields = ['date_start', 'campaign_id', 'campaign_name', 'spend', 'impressions', 'clicks']
bq_client = bigquery.Client(project=PROJECT_ID)

# Перевіряємо/створюємо датасет
dataset_ref = bq_client.dataset(DATASET_ID)
try:
    bq_client.get_dataset(dataset_ref)
except Exception:
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = "EU"
    bq_client.create_dataset(dataset)

# Проходимося по кожному кабінету
for name, config in ACCOUNTS.items():
    ad_account_id = config["ad_account_id"]
    table_id = config["table_id"]
    
    if not ad_account_id:
        print(f"Пропускаємо кабінет '{name}': не вказано ID.")
        continue

    print(f"\n--- Обробка кабінету {name} ({ad_account_id}) ---")
    account = AdAccount(ad_account_id)

    print(f"Отримуємо витрати з {start_date} по {end_date}...")
    try:
        insights = account.get_insights(fields=fields, params=date_preset_params)
    except Exception as e:
        print(f"Помилка при запиті до Meta API для {name}: {e}")
        continue

    rows_to_insert = []
    for item in insights:
        rows_to_insert.append({
            "date": item.get('date_start'),
            "campaign_id": str(item.get('campaign_id')),
            "campaign_name": item.get('campaign_name'),
            "spend": float(item.get('spend', 0.0)),
            "impressions": int(item.get('impressions', 0)),
            "clicks": int(item.get('clicks', 0)),
            "updated_at": datetime.datetime.utcnow().isoformat()
        })

    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_id}"
    print(f"Знайдено {len(rows_to_insert)} рядків. Завантажуємо в таблицю {table_id}...")

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )

    job = bq_client.load_table_from_json(rows_to_insert, table_ref, job_config=job_config)
    job.result()

    print(f"УСПІШНО! Таблицю {table_ref} оновлено в BigQuery!")

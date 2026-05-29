import datetime
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from app.config.src import COSMOS_ENDPOINT, COSMOS_KEY, DATABASE_NAME, CONTAINER_NAME

async def save_final_payload_to_cosmos(payload: dict):
    """
    Saves the strictly formatted final payload to Azure Cosmos DB.
    Enforces Cosmos-required fields (id and partition key).
    """
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        print("[Cosmos] Skipping save: Endpoint or Key missing in configuration.")
        return

    try:
        async with CosmosClient(COSMOS_ENDPOINT, credential=COSMOS_KEY) as client:
            db = client.get_database_client(DATABASE_NAME)
            container = db.get_container_client(CONTAINER_NAME)
            
            document = payload.copy()
            
            # Enforce Cosmos DB system fields
            document["id"] = payload.get("case_id") or payload.get("call_id")
            document["user_id"] = payload.get("customer_number")
            
            # Add a storage timestamp
            document["stored_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            
            await container.upsert_item(document)
            print(f"[Cosmos] Successfully stored clean result for {document['id']}")
            
    except CosmosHttpResponseError as e:
        print(f"[Cosmos] Failed to save result. Error: {e.message}")
    except Exception as e:
        print(f"[Cosmos] Unexpected Error: {e}")
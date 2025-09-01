import uuid
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from starlette.responses import Response
from starlette import status

from server.core import storage
from server.core.models import (
    CreateCampaignRequest, CampaignMeta, CampaignJournal, Message,
    CampaignDetailsResponse, AddJournalEntryRequest
)
from server.api.auth import get_current_user_code

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post("", response_model=CampaignMeta)
async def create_campaign(
    request: CreateCampaignRequest,
    user_code: str = Depends(get_current_user_code)
):
    """Creates a new campaign for the logged-in user."""
    campaigns_dir = storage.get_campaigns_dir(user_code)
    if not campaigns_dir:
        raise HTTPException(status_code=400, detail="Invalid user code.")

    campaigns_dir.mkdir(exist_ok=True)

    new_campaign_meta = CampaignMeta(
        name=request.name,
        tone=request.tone,
        difficulty=request.difficulty,
        host_user_code=user_code,
    )

    # Save meta file
    meta_path = storage.get_campaign_meta_file(user_code, str(new_campaign_meta.id))
    storage.write_json(meta_path, new_campaign_meta.dict())

    # Save initial empty journal
    journal_path = storage.get_campaign_journal_file(user_code, str(new_campaign_meta.id))
    initial_journal = CampaignJournal()
    storage.write_json(journal_path, initial_journal.dict())

    return new_campaign_meta


@router.get("", response_model=list[CampaignMeta])
async def list_user_campaigns(user_code: str = Depends(get_current_user_code)):
    """Lists all campaigns belonging to the current user."""
    campaigns_dir = storage.get_campaigns_dir(user_code)
    if not campaigns_dir or not campaigns_dir.exists():
        return []

    campaign_metas = []
    for camp_dir in campaigns_dir.iterdir():
        if camp_dir.is_dir() and (camp_dir / "meta.json").exists():
            meta_data = storage.read_json(camp_dir / "meta.json")
            if meta_data:
                campaign_metas.append(CampaignMeta(**meta_data))

    return campaign_metas


@router.get("/{campaign_id}", response_model=CampaignDetailsResponse)
async def get_campaign_details(
    campaign_id: str,
    user_code: str = Depends(get_current_user_code)
):
    """Retrieves the metadata and journal for a specific campaign."""
    meta_path = storage.get_campaign_meta_file(user_code, campaign_id)
    journal_path = storage.get_campaign_journal_file(user_code, campaign_id)

    if not meta_path or not journal_path:
        raise HTTPException(status_code=400, detail="Invalid campaign ID format.")

    meta_data = storage.read_json(meta_path)
    journal_data = storage.read_json(journal_path)

    if not meta_data or not journal_data:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    return CampaignDetailsResponse(
        meta=CampaignMeta(**meta_data),
        journal=CampaignJournal(**journal_data)
    )

@router.post("/{campaign_id}/journal", response_model=CampaignJournal)
async def add_journal_entry(
    campaign_id: str,
    request: AddJournalEntryRequest,
    user_code: str = Depends(get_current_user_code)
):
    """Adds a new entry to the campaign's journal."""
    journal_path = storage.get_campaign_journal_file(user_code, campaign_id)
    if not journal_path:
        raise HTTPException(status_code=400, detail="Invalid campaign ID format.")

    journal_data = storage.read_json(journal_path)
    if journal_data is None:
        raise HTTPException(status_code=404, detail="Campaign journal not found.")

    journal = CampaignJournal(**journal_data)
    journal.entries.append(request.message)

    storage.write_json(journal_path, journal.dict())

    return journal

@router.post("/{campaign_id}/checkpoint")
async def save_campaign_checkpoint(
    campaign_id: str,
    user_code: str = Depends(get_current_user_code)
):
    """Saves a snapshot of the current campaign state."""
    # For this project, the journal is saved on every update, so this is more of a placeholder.
    # A full implementation would save the journal and meta to a timestamped file.
    campaign_details = await get_campaign_details(campaign_id, user_code)

    checkpoints_dir = journal_path = storage.get_campaign_journal_file(user_code, campaign_id).parent / "checkpoints"
    checkpoints_dir.mkdir(exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
    checkpoint_file = checkpoints_dir / f"{timestamp}.json"

    storage.write_json(checkpoint_file, campaign_details.dict())

    return {"message": "Checkpoint saved successfully", "file": str(checkpoint_file)}


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: str,
    user_code: str = Depends(get_current_user_code)
):
    """Deletes a user's campaign, including all its data."""
    campaigns_dir = storage.get_campaigns_dir(user_code)
    if not campaigns_dir:
        raise HTTPException(status_code=400, detail="Invalid user code.")

    try:
        # Validate campaign_id format
        uuid.UUID(campaign_id)
        campaign_path = campaigns_dir / f"camp_{campaign_id}"

        if not campaign_path.exists() or not campaign_path.is_dir():
            raise HTTPException(status_code=404, detail="Campaign not found.")

        shutil.rmtree(campaign_path)

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid campaign ID format.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete campaign: {e}")

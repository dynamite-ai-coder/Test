import os
import asyncio
from datetime import datetime
from database import update_job, get_job
from telethon_client import get_client, start_client, search_channel, download_file
from terabox_uploader import upload_file, verify_upload
from configuration import DOWNLOAD_DIR, MIN_SIZE_BYTES, MAX_SIZE_BYTES
from job_queue import is_stop_requested


def process_job(job_id, user_id, channel):
    print(f"[WORKER] Starting job {job_id} for {channel}")
    update_job(job_id, status="running", started_at=datetime.utcnow().isoformat())
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run_job(job_id, channel))
        loop.close()
    except Exception as e:
        print(f"[WORKER] Job {job_id} failed: {e}")
        update_job(job_id, status="failed", error_message=str(e))


async def _run_job(job_id, channel):
    try:
        await start_client()
    except Exception as e:
        print(f"[WORKER] Telethon connection failed: {e}")
        update_job(job_id, status="failed", error_message=f"Telethon error: {e}")
        return
    try:
        messages = await search_channel(channel)
    except Exception as e:
        print(f"[WORKER] Search failed for {channel}: {e}")
        update_job(job_id, status="failed", error_message=f"Search error: {e}")
        return
    txt_messages = []
    for msg in messages:
        if is_stop_requested():
            update_job(job_id, status="stopped")
            return
        if msg.document:
            filename = msg.file.name if msg.file else ""
            if filename.lower().endswith(".txt"):
                size = msg.document.size or 0
                if MIN_SIZE_BYTES <= size <= MAX_SIZE_BYTES:
                    txt_messages.append((msg, filename, size))
    update_job(job_id, files_found=len(txt_messages))
    uploaded = 0
    failed = 0
    for msg, filename, size in txt_messages:
        if is_stop_requested():
            update_job(job_id, status="stopped")
            return
        dest = os.path.join(DOWNLOAD_DIR, f"{job_id}_{filename}")
        update_job(job_id, current_file=filename)
        try:
            print(f"[DOWNLOAD] Downloading {filename} ({size} bytes)")
            await download_file(msg, dest)
            print(f"[UPLOAD] Uploading {filename} to TeraBox")
            success, err = upload_file(dest, filename)
            if success:
                uploaded += 1
                print(f"[UPLOAD] Verified: {filename}")
            else:
                failed += 1
                print(f"[UPLOAD] Failed {filename}: {err}")
        except Exception as e:
            failed += 1
            print(f"[WORKER] Error processing {filename}: {e}")
        finally:
            if os.path.exists(dest):
                os.remove(dest)
                print(f"[WORKER] Cleaned up {dest}")
        update_job(job_id, files_uploaded=uploaded, files_failed=failed)
    update_job(
        job_id,
        status="completed",
        finished_at=datetime.utcnow().isoformat(),
        current_file=None,
    )
    print(f"[WORKER] Job {job_id} completed: {uploaded} uploaded, {failed} failed")

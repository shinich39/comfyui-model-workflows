"""
@author: shinich39
@title: comfyui-model-workflows
@nickname: comfyui-model-workflows
@version: 1.0.2
@description: Load model creator's workflow.
"""

import os
import json
import hashlib
import traceback
import requests
import gzip
import io
import folder_paths

from server import PromptServer
from aiohttp import web

WEB_DIRECTORY = "./js"
__DIRNAME = os.path.dirname(os.path.abspath(__file__))
REPO_URL = "https://github.com/shinich39/civitai-model-json"
LATEST_DATA_URL = "https://raw.githubusercontent.com/shinich39/civitai-model-json/refs/heads/main/dist/latest.json"
LATEST_DATA_PATH = os.path.join(__DIRNAME, "latest.json")
CKPT_DATA_URL = "https://raw.githubusercontent.com/shinich39/civitai-model-json/refs/heads/main/dist/checkpoints.json.gz"
CKPT_DATA_PATH = os.path.join(__DIRNAME, "checkpoints.json")
HASH_DATA_PATH = os.path.join(__DIRNAME, "hashes.json")
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

def get_model_hash(file_path):
  with open(file_path, "rb") as f:
    return hashlib.sha256(f.read()).hexdigest().upper()
  
def get_model_hashes():
  hashes = {}
  if os.path.exists(HASH_DATA_PATH) == True:
    with open(HASH_DATA_PATH, "r") as f:
      hashes = json.load(f)

  for file_rel_path in folder_paths.get_filename_list("checkpoints"):
    file_name = os.path.basename(file_rel_path)
    file_path = folder_paths.get_full_path("checkpoints", file_rel_path)

    if file_name not in hashes:
      print(f"[comfyui-model-workflows] Hash not found: {file_name}")
      print(f"[comfyui-model-workflows] Creating hash...")
      hashes[file_name] = get_model_hash(file_path)
      update_model_hashes(hashes)

  return hashes

def update_model_hashes(hashes):
  with open(HASH_DATA_PATH, "w") as f:
    f.write(json.dumps(hashes, indent=2))
    f.close()
  
def get_remote_latest():
  try:
    res = requests.get(LATEST_DATA_URL)
    data = json.loads(res.text)
    return data
  except Exception:
    return None
  
def get_local_latest():
  try:
    if os.path.exists(LATEST_DATA_PATH) == True:
      with open(LATEST_DATA_PATH, "r") as f:
        return json.load(f)
  except Exception:
    return None

def get_ckpt_json():
  # Check updates
  remote_data = get_remote_latest()
  local_data = get_local_latest()

  remote_time = None
  local_time = None
  if remote_data != None and "updatedAt" in remote_data:
    remote_time = remote_data["updatedAt"]

  if local_data != None and "updatedAt" in local_data:
    local_time = local_data["updatedAt"]

  is_updated = os.path.exists(CKPT_DATA_PATH) == False or local_time != remote_time

  if is_updated == False:
    with open(CKPT_DATA_PATH, "r") as file:
      print(f"[comfyui-model-workflows] No updates found: {local_time} = ${remote_time}")
      return json.load(file)
    
  # Save latest.json
  with open(LATEST_DATA_PATH, "w") as f:
    f.write(json.dumps(remote_data))
    f.close()
  
  # Dowlolad checkpoints.json
  print(f"[comfyui-model-workflows] New update available: {local_time} < {remote_time}")
  print(f"[comfyui-model-workflows] Downloading checkpoints.json.gz...")

  try:
    res = requests.get(CKPT_DATA_URL)
    print(f"[comfyui-model-workflows] Decompressing checkpoints.json.gz...")
    with gzip.GzipFile(fileobj=io.BytesIO(res.content)) as f:
      decompressed_data = f.read()

    text = decompressed_data.decode('utf-8')
    data = json.loads(text)
    with open(CKPT_DATA_PATH, "w") as f:
      f.write(json.dumps(data))
      f.close()

    print(f"[comfyui-model-workflows] checkpoints.json has been downloaded")

    return data
  except Exception:
    print(traceback.format_exc())
    print(f"[comfyui-model-workflows] Failed to download.")

    if os.path.exists(CKPT_DATA_PATH) == True:
      with open(CKPT_DATA_PATH, "r") as file:
        return json.load(file)
      
    return []

@PromptServer.instance.routes.get("/shinich39/comfyui-model-workflows/load")
async def load(request):
  try:
    hashes = get_model_hashes()
    ckpts = get_ckpt_json()

    # Filtering
    filtered_ckpts = {}
    for file_rel_path in folder_paths.get_filename_list("checkpoints"):
      file_name = os.path.basename(file_rel_path)
      hash = hashes[file_name]
      name = file_rel_path
      for ckpt in ckpts:
        if hash in ckpt["hashes"]:
          filtered_ckpts[name] = ckpt
          break
        elif name in ckpt["files"]:
          filtered_ckpts[name] = ckpt
          break

    return web.json_response({
      "checkpoints": filtered_ckpts
    })
  except Exception:
    print(traceback.format_exc())
    return web.Response(status=400)


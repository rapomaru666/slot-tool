import json

from buffer_client import delete_post

WRONG_BUFFER_POST_ID = "6a9b8922dca05898bf4a1ebb"

output = delete_post(WRONG_BUFFER_POST_ID)
print(json.dumps({"ok": True, **output}, ensure_ascii=False, indent=2))

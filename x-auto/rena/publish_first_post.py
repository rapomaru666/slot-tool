import json

from buffer_client import publish_post

IMAGE_URL = "https://static.metricool.com/planner/202609/6760386-file-11754633307708686853.jpeg"
TEXT = """X始めました〜！🙌✨

いろんな人とたくさん話せたらうれしいです☺️
気軽に話しかけてください🫶

よろしくお願いします！"""

output = publish_post(TEXT, image_url=IMAGE_URL)
print(json.dumps({"ok": True, **output}, ensure_ascii=False, indent=2))

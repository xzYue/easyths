import json
from urllib.request import Request, urlopen

BASE = 'http://192.168.77.28:7648'

# 提交资金查询
submit_url = f"{BASE}/api/v1/operations/funds_query"
req = Request(submit_url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
with urlopen(req, timeout=20) as resp:
    submit_text = resp.read().decode("utf-8", errors="replace")
print("submit:", submit_text)

submit_obj = json.loads(submit_text)
op_id = submit_obj["data"]["operation_id"]
print("operation_id:", op_id)

# 阻塞拿结果
result_url = f"{BASE}/api/v1/operations/{op_id}/result?timeout=30"
req2 = Request(result_url, method="GET")
with urlopen(req2, timeout=40) as resp2:
    result_text = resp2.read().decode("utf-8", errors="replace")
print("result:", result_text)

# 尝试提取可用资金字段
obj = json.loads(result_text)
data = obj.get("data", {}) if isinstance(obj, dict) else {}
candidates = [
    "available", "available_cash", "available_amount", "balance_available",
    "可用", "可用资金", "可用金额"
]
found = {k: data.get(k) for k in candidates if isinstance(data, dict) and k in data}
print("available_candidates:", found)
if isinstance(data, dict):
    print("all_data_keys:", list(data.keys()))

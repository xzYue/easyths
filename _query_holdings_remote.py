import json
from urllib.request import Request, urlopen

BASE = 'http://192.168.77.28:7648'

# 提交持仓查询（指定返回 json）
submit_url = f"{BASE}/api/v1/operations/holding_query"
payload = json.dumps({"params": {"return_type": "json"}}).encode("utf-8")
req = Request(submit_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
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

obj = json.loads(result_text)
data = obj.get("data") if isinstance(obj, dict) else None

if isinstance(data, list):
    print("positions_count:", len(data))
elif isinstance(data, dict):
    # 某些实现会把持仓放在 data["positions"] 里
    positions = data.get("positions")
    if isinstance(positions, list):
        print("positions_count:", len(positions))
    else:
        print("data_keys:", list(data.keys()))
else:
    print("data_type:", type(data).__name__)

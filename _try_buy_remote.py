import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = 'http://192.168.77.28:7648'

payload = {
    "params": {
        "stock_code": "920185",
        "price": 30.53,
        "quantity": 100
    }
}

# 1) 提交买单
submit_url = f"{BASE}/api/v1/operations/buy"
req = Request(
    submit_url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urlopen(req, timeout=20) as resp:
    submit_text = resp.read().decode("utf-8", errors="replace")

print("submit:", submit_text)
submit_obj = json.loads(submit_text)
op_id = submit_obj.get("data", {}).get("operation_id")
print("operation_id:", op_id)

if not op_id:
    raise SystemExit("No operation_id returned")

# 2) 获取执行结果
result_url = f"{BASE}/api/v1/operations/{op_id}/result?timeout=30"
req2 = Request(result_url, method="GET")

try:
    with urlopen(req2, timeout=40) as resp2:
        result_text = resp2.read().decode("utf-8", errors="replace")
    print("result:", result_text)
except HTTPError as e:
    print("result_http_error:", e.code)
    print(e.read().decode("utf-8", errors="replace"))

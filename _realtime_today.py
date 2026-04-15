import json
from urllib.request import Request, urlopen
from datetime import datetime

BASE = 'http://192.168.77.28:7648'

def query_op(op_name, params=None):
    """查询操作并阻塞等结果"""
    payload = {"params": params or {}}
    submit_url = f"{BASE}/api/v1/operations/{op_name}"
    req = Request(
        submit_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urlopen(req, timeout=20) as resp:
        submit_obj = json.loads(resp.read().decode("utf-8", errors="replace"))
    op_id = submit_obj["data"]["operation_id"]
    
    result_url = f"{BASE}/api/v1/operations/{op_id}/result?timeout=30"
    req2 = Request(result_url, method="GET")
    with urlopen(req2, timeout=40) as resp2:
        result_obj = json.loads(resp2.read().decode("utf-8", errors="replace"))
    return result_obj.get("data")

print("="*80)
print("【实时账户状态】", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("="*80)

# 1. 资金
funds = query_op("funds_query")
print("\n【可用资金】")
for k, v in funds.items():
    print(f"  {k}: {v}")

# 2. 持仓
holdings = query_op("holding_query", {"return_type": "json"})
print(f"\n【持仓明细】({len(holdings)} 条)")
for h in holdings:
    if h.get("市值") and float(h.get("市值", 0)) > 0:
        print(f"  {h.get('证券代码')} {h.get('证券名称')}: "
              f"实际数量={h.get('实际数量')}, 市值={h.get('市值')}, "
              f"盈亏={h.get('盈亏')}, 仓位={h.get('仓位占比(%)')}")

"""
coze_workload_identity shim —— 标准 requests 转发
让 variant-literature-patient 技能在缺少 Coze 平台特有模块的环境下开箱即用。
coze_workload_identity.requests 与标准 requests 接口完全一致。
"""
import requests as _requests

# 显式导出 requests 名（供 `from coze_workload_identity import requests`）
requests = _requests

# 转发标准 requests 的常用公开接口
request = _requests.request
get = _requests.get
post = _requests.post
put = _requests.put
delete = _requests.delete
head = _requests.head
patch = _requests.patch
options = _requests.options
Session = _requests.Session
__version__ = _requests.__version__

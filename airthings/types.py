from typing import Dict, Union, List

JSONPrimitive = Union[int, float, str, None]
JSONArray = List["JSONAny"]
JSONObj = Dict[str, "JSONAny"]
JSONAny = Union[JSONPrimitive, JSONArray, JSONObj]

"""
鎻愪緵鏂囦欢鍚嶆竻娲楃瓑杞婚噺绾ф枃浠跺伐鍏峰嚱鏁般€?
"""
import re

SAFE_FILENAME_PATTERN: re.Pattern[str] = re.compile(r"[^A-Za-z0-9_.-]+")


def sanitize_filename(filename: str) -> str:
    """娓呮礂鏂囦欢鍚嶏紝閬垮厤鐗规畩瀛楃褰卞搷钀界洏銆?

    Args:
        filename: 鍘熷鏂囦欢鍚嶃€?

    Returns:
        str: 浠呬繚鐣欏畨鍏ㄥ瓧绗﹀悗鐨勬枃浠跺悕銆?
    """

    return SAFE_FILENAME_PATTERN.sub("_", filename)


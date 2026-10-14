"""Normalize explicitly labeled factory-profile claims without inferring capacity."""
import re

FACTORY_FIELDS = {
    "成立时间", "年交易额", "员工总数", "定制起订量", "贴牌起订量", "接外贸订单", "加工方式", "增值税发票",
    "企业面积", "工厂面积", "厂房面积", "生产线数量", "设备总数", "经营模式",
}


def normalize_factory_claims(claims):
    result = {"factory_profile_claims": dict(claims)}
    # A company floor area may be an office/warehouse; it is not factory area.
    fields = {
        "企业面积": ("company_area_sqm", r"([0-9]+(?:\.[0-9]+)?)\s*(?:m²|m2|㎡|平方米)"),
        "工厂面积": ("factory_area_sqm", r"([0-9]+(?:\.[0-9]+)?)\s*(?:m²|m2|㎡|平方米)"),
        "厂房面积": ("factory_area_sqm", r"([0-9]+(?:\.[0-9]+)?)\s*(?:m²|m2|㎡|平方米)"),
        "生产线数量": ("production_line_count", r"([0-9]+)\s*(?:条|条生产线)?"),
        "设备总数": ("equipment_count", r"([0-9]+)\s*(?:台|台设备)?"),
    }
    for label, (field, pattern) in fields.items():
        match = re.fullmatch(pattern, claims.get(label, ""))
        if match and float(match[1]) > 0:
            value = float(match[1])
            if field not in result or result[field] == value:
                result[field] = value
            else:
                # Conflicting aliases are retained as claims, not numeric facts.
                result.pop(field, None)
    if claims.get("员工总数"):
        result["employee_count_display_text"] = claims["员工总数"]
    if claims.get("加工方式"):
        result["processing_methods_display_text"] = claims["加工方式"]
    if claims.get("经营模式"):
        result["business_type"] = claims["经营模式"]
    return result


def stored_factory_claims(company):
    """Also read older captures whose labeled claims were stored as display text."""
    claims = company.get("factory_profile_claims")
    if isinstance(claims, dict):
        return {k: v for k, v in claims.items() if k in FACTORY_FIELDS and isinstance(v, str)}
    text = company.get("factory_profile_claims_display_text")
    if not isinstance(text, str):
        return {}
    return {name.strip(): value.strip() for part in text.split(";") if ":" in part
            for name, value in [part.split(":", 1)] if name.strip() in FACTORY_FIELDS}

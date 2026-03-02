"""支付模块自定义异常"""


class PaymentError(Exception):
    """支付模块基础异常"""


class InvalidPlanError(PaymentError):
    """无效的订阅方案"""


class OrderNotFoundError(PaymentError):
    """订单不存在"""


class OrderExpiredError(PaymentError):
    """订单已过期"""


class AlipayError(PaymentError):
    """支付宝接口错误"""

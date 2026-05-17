import { request } from '@/utils/request'

export function getPaymentProducts() {
  return request({
    url: '/api/payment/products',
    method: 'GET'
  })
}

export function createOrder({
  tier,
  billing_cycle,
  product_type = 'subscription',
  product_code = null,
  payment_method = null
}) {
  return request({
    url: '/api/payment/orders',
    method: 'POST',
    data: { tier, billing_cycle, product_type, product_code, payment_method }
  })
}

export function notifyPaid(orderId) {
  return request({
    url: `/api/payment/orders/${orderId}/notify`,
    method: 'POST'
  })
}

export function getPaymentOrder(orderId) {
  return request({
    url: `/api/payment/orders/${orderId}`,
    method: 'GET'
  })
}

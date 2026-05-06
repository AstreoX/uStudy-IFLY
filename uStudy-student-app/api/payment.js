import { request } from '@/utils/request'

export function getPaymentProducts() {
  return request({
    url: '/api/payment/products',
    method: 'GET'
  })
}

export function createOrder({ tier, billing_cycle, product_type = 'subscription', product_code = null }) {
  return request({
    url: '/api/payment/orders',
    method: 'POST',
    data: { tier, billing_cycle, product_type, product_code }
  })
}

export function notifyPaid(orderId) {
  return request({
    url: `/api/payment/orders/${orderId}/notify`,
    method: 'POST'
  })
}

import { request } from '@/utils/request'

export function createOrder({ tier, billing_cycle }) {
  return request({
    url: '/api/payment/orders',
    method: 'POST',
    data: { tier, billing_cycle }
  })
}

export function getOrderStatus(orderId) {
  return request({
    url: `/api/payment/orders/${orderId}`,
    method: 'GET'
  })
}

export function listOrders() {
  return request({
    url: '/api/payment/orders',
    method: 'GET'
  })
}

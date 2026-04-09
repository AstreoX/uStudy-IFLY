import { request } from '@/utils/request'

/**
 * 获取用户所有 MCP 服务
 * @returns {Promise<Object>} { services: [McpService] }
 */
export function getMcpServices() {
  return request({
    url: '/api/mcp-services',
    method: 'GET'
  })
}

/**
 * 创建 MCP 服务
 * @param {Object} data - { name: string, url: string, api_key?: string }
 * @returns {Promise<Object>} McpService
 */
export function createMcpService(data) {
  return request({
    url: '/api/mcp-services',
    method: 'POST',
    data
  })
}

/**
 * 更新 MCP 服务
 * @param {string} serviceId - MCP 服务 ID
 * @param {Object} data - { name?: string, url?: string, api_key?: string, enabled?: boolean }
 * @returns {Promise<Object>} McpService
 */
export function updateMcpService(serviceId, data) {
  return request({
    url: `/api/mcp-services/${serviceId}`,
    method: 'PATCH',
    data
  })
}

/**
 * 删除 MCP 服务
 * @param {string} serviceId - MCP 服务 ID
 * @returns {Promise<void>}
 */
export function deleteMcpService(serviceId) {
  return request({
    url: `/api/mcp-services/${serviceId}`,
    method: 'DELETE'
  })
}

/**
 * 测试 MCP 连接 + 工具发现
 * @param {Object} data - { url: string, api_key?: string }
 * @returns {Promise<Object>} { success: boolean, tools: [{ name, description }], error?: string }
 */
export function testMcpConnection(data) {
  return request({
    url: '/api/mcp-services/test-connection',
    method: 'POST',
    data
  })
}

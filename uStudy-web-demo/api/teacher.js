import { request } from '@/utils/request'

export function getTeacherOverview(spaceId, days = 7) {
  return request({ url: `/api/teacher/spaces/${spaceId}/overview`, method: 'GET', data: { days } })
}

export function getTeacherKnowledge(spaceId, days = 7) {
  return request({ url: `/api/teacher/spaces/${spaceId}/knowledge`, method: 'GET', data: { days } })
}

export function getTeacherStudents(spaceId, params = {}) {
  return request({ url: `/api/teacher/spaces/${spaceId}/students`, method: 'GET', data: params })
}

export function getTeacherStudentDetail(spaceId, studentId, days = 7) {
  return request({
    url: `/api/teacher/spaces/${spaceId}/students/${studentId}`,
    method: 'GET',
    data: { days }
  })
}

import { request } from '@/utils/request'

export function getCalendarEvents(startDate, endDate) {
  return request({
    url: `/api/calendar/events?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
    method: 'GET'
  })
}

export function createCalendarEvent(data) {
  return request({
    url: '/api/calendar/events',
    method: 'POST',
    data
  })
}

export function updateCalendarEvent(eventId, data) {
  return request({
    url: `/api/calendar/events/${eventId}`,
    method: 'PATCH',
    data
  })
}

export function deleteCalendarEvent(eventId) {
  return request({
    url: `/api/calendar/events/${eventId}`,
    method: 'DELETE'
  })
}

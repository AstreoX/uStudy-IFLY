import { getDefaultSpace } from '@/api/space'


export async function openDefaultSpace() {
  const space = await getDefaultSpace()
  if (!space?.id) {
    throw new Error('默认数据结构课程尚未初始化')
  }
  uni.reLaunch({
    url: `/pages/study/study?spaceId=${encodeURIComponent(space.id)}`
  })
  return space
}

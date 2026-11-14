import { describe, expect, it } from 'vitest'
import { toParams } from './client'

describe('toParams', () => {
  it('omits empty values but keeps zero and false', () => {
    expect(toParams({ q: 'web', favorite: true, page: 2, group_id: '' })).toEqual({
      q: 'web',
      favorite: 'true',
      page: '2',
    })
    expect(toParams({})).toEqual({})
  })
})

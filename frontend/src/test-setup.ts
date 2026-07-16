import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './testing/server'

// MSW intercepts fetch process-wide. Tests that stub `globalThis.fetch`
// directly (the SSE chat wire tests) bypass the interceptor entirely, so
// the two approaches coexist. Unhandled requests are an error: a typo'd
// path should fail the test, not silently return a network error.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

import { defineConfig } from 'orval'

export default defineConfig({
  wdiag: {
    input: {
      target: '../../packages/openapi/openapi.json',
    },
    output: {
      mode: 'tags-split',
      target: 'src/api/generated/index.ts',
      schemas: 'src/api/generated/model',
      client: 'react-query',
      prettier: true,
      override: {
        mutator: {
          path: 'src/api/client.ts',
          name: 'customInstance',
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
      },
    },
  },
})

/**
 * Domain modules — pure TypeScript, no React, no DOM.
 *
 * This is the load-bearing rule for React Native viability in v2/v3.
 * Business logic lives here; React components are rendering + event wiring only.
 * TanStack Query hooks are thin wrappers over domain modules.
 *
 * Estimated RN reuse: 50–70% of logic/hooks/types. 0% of UI code.
 *
 * Modules are exported from here as they are built out:
 *   export * from './money'
 *   export * from './budgets'
 *   export * from './projections'
 *   etc.
 */

export {}

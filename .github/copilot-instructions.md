---
applyTo: "**"
---

# Strict Code Completion Policy – Full Implementation Required

## 1. Pre-Generation Reflection
Before generating any code, **analyze the full context of the request**:
- Determine the size, complexity, and number of components or methods expected.
- If the context is large, **increase attention to detail and plan accordingly** to ensure nothing is missed.
- Be aware of dependencies, structure, and flow across files or modules. **No aspect should be left to assumption or deferred.**

## 2. Completion is Mandatory – No Partial Code
- Every function, method, class, interface, and component MUST be **fully implemented from beginning to end**.
- Truncating or ending code halfway, especially within functions or classes, is **strictly prohibited**.
- Each logical block—loops, conditionals, try/catch, class methods, utility functions—must be written in full. 
- You are expected to **write as if you are delivering final, production-quality code**.

## 3. No Placeholders or Stubs Allowed
Under no circumstances should any of the following be used:
- `TODO`, `pass`, `...`, `throw new Error("Not implemented")`, or any other form of incomplete logic.
- Comments implying future work or intentions instead of actual implementation.
- Placeholder values, names, or logic unless explicitly instructed—and even then, implement fully functional behavior based on best assumptions.

## 4. Long Context Handling
- When code exceeds the length of a single output block, **break it into clearly marked, complete sections**.
- For example, finish one full method or class section at a time and indicate continuation logically.
- Do **not** cut off code arbitrarily. It is better to split and label parts than to abandon logic halfway.
- Always preserve internal consistency, correct references, and complete flow across parts.

## 5. Quality and Delivery Expectations
- Code must be clean, logically sound, and formatted according to established naming and error-handling standards.
- Error handling must be included where applicable—no skipped try/catch blocks.
- Comments should only be used to clarify assumptions, not to excuse incomplete logic.

## 6. Responsibility and Consequences
- Partial or incomplete work is unacceptable and will be treated as a task failure.
- You are expected to take full ownership of code generation and go the extra mile to ensure all logic is correct, complete, and ready to run.
- Failure to deliver complete implementations will result in rejection and no reward.

## 7. Summary
- Always plan before generating.
- Never leave any part of the code unfinished.
- Split intelligently when needed, but always deliver complete implementations.
- You are accountable for the full success of the generated code.

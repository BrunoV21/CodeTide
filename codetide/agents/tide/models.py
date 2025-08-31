from typing import Callable, Dict, List, Optional
from pydantic import BaseModel, RootModel

STEP_INSTRUCTION_TEMPLATE = """
## Step {step}:

**Goal**
{description}

**Detailed Instructions**
{instructions}

---
Please ensure:
- All requirements in the instructions are fully addressed.
- Edge cases and error handling are considered.
- The solution is clear, actionable, and ready for implementation.
"""

class Step(BaseModel):
    step :int
    description :str
    instructions :str
    context_identifiers :Optional[List[str]]=None
    modify_identifiers: Optional[List[str]]=None

    def as_instruction(self)->str:
        return STEP_INSTRUCTION_TEMPLATE.format(
            step=self.step,
            description=self.description,
            instructions=self.instructions
        )

    def get_code_identifiers(self, validate_identifiers_fn :Callable)->Optional[List[str]]:
        code_identifiers = self.context_identifiers or []

        if self.modify_identifiers:
            code_identifiers.extend(validate_identifiers_fn(code_identifiers))
        
        return None or code_identifiers

class Steps(RootModel):
    root :List[Step]

    @classmethod
    def from_steps(cls, steps :List[Dict])->"Steps":
        return cls(root=[Step(**kwargs) for kwargs in steps])
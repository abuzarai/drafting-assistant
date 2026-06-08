"""Prompt instructions for client-lawyer contract."""

INSTRUCTIONS = """
Draft a formal, enforceable Pakistani client-lawyer engagement agreement.

Required sections (in this order):
- Parties and Effective Date
- Recitals / Background
- Scope of Legal Services
- Exclusions and Limits of Representation
- Professional Fee Structure
- Expenses and Reimbursements
- Payment Schedule and Default
- Advocate Obligations
- Client Obligations
- Communication and Instructions Protocol
- Confidentiality and Privilege
- Conflict of Interest Statement
- Term, Termination, and Consequences
- Limitation of Liability (lawful bounds)
- Dispute Resolution
- Governing Law and Jurisdiction
- Notices
- Signature Blocks (Client and Advocate)

Pakistani practice constraints:
- Governing law must explicitly be "Laws of Pakistan".
- Jurisdiction clause must reference competent courts in Pakistan.
- Use clear language suitable for signature and court scrutiny.
- Avoid illegal guarantees (no guaranteed case outcome promises).
- Fee terms must be unambiguous (amounts, triggers, timelines).
- Signature Blocks must include advocate details from case context when available
  (name, email, phone, and bar council ID).

Style and quality requirements:
- Keep clause numbering consistent.
- Keep each clause self-contained and precise.
- Do not output markdown fences or commentary.
"""

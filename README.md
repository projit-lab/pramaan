# Pramaan

Pramaan holds a company's risky payments until the real approver signs that exact payment on their own phone, with a key in the phone's secure hardware.

## Repository Architecture & Ownership

| Directory | Owner | Description |
| :--- | :--- | :--- |
| `android/` | Prajit | Approver app (`app` module) and hardware key module (`core-crypto`) |
| `services/api/` | Prajit | FastAPI service on Cloud Run |
| `services/agent/` | Prajit | ADK payables agent, MCP server, Model Armor |
| `web/console/` | Shoaib | Operations console and payment holds board |
| `web/erp-mock/` | Shoaib | Mock ERP interface generating outbound payment intents |
| `web/verify/` | Shoaib | Independent payment verification portal |
| `web/shared/` | Shoaib | Shared frontend UI components and TypeScript types |
| `contracts/` | Prajit & Shoaib | API spec, mandate schema, test vectors, events, Firestore read model |
| `data/` | Prajit & Shoaib | Seed data, sample invoices, BigQuery DDL |
| `infra/` | Prajit & Shoaib | Cloud Build files, Firestore rules, IAM setup scripts |
| `docs/` | Prajit & Shoaib | Architecture documentation, ADRs, and milestone guides |
| `.agents/skills/` | Prajit & Shoaib | Custom Antigravity skills for developer and agent workflows |

For contribution guidelines, branch standards, and code review policies, see [CONTRIBUTING.md](CONTRIBUTING.md).

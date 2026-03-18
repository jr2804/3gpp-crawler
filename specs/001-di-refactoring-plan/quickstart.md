# Quick Start: Dependency Injection Refactoring Planning

**Date**: 2026-03-02\
**Feature**: Dependency Injection Refactoring Planning\
**Branch**: `001-di-refactoring-plan`

## Overview

This guide provides a quick start to understanding and using the DI refactoring planning for tdoc-crawler. The planning includes architectural analysis, DI design, implementation roadmap, and stakeholder validation.

## What's Included

### Planning Documents

| Document | Purpose | Location |
|----------|---------|----------|
| **spec.md** | Feature specification with requirements | `specs/001-di-refactoring-plan/spec.md` |
| **plan.md** | Implementation plan with technical details | `specs/001-di-refactoring-plan/plan.md` |
| **research.md** | Research findings and decisions | `specs/001-di-refactoring-plan/research.md` |
| **data-model.md** | Data model and entity definitions | `specs/001-di-refactoring-plan/data-model.md` |
| **contracts/** | API contracts and interfaces | `specs/001-di-refactoring-plan/contracts/` |

### Directory Structure

```
specs/001-di-refactoring-plan/
├── spec.md                    # Feature specification
├── plan.md                    # Implementation plan  
├── research.md                # Research findings
├── data-model.md              # Data model
├── quickstart.md              # This guide
├── checklists/                # Quality checklists
│   └── requirements.md        # Specification quality checklist
├── contracts/                 # API contracts
│   └── service-container-api.md  # ServiceContainer API
├── analysis/                  # Architectural analysis (to be created)
├── design/                    # DI design documents (to be created)
└── roadmap/                   # Implementation roadmap (to be created)
```

## Key Concepts

### 1. ServiceContainer

Central container managing lifecycle of core services:

- CacheManager registration and access
- Database factory methods (TDocDatabase, SpecDatabase)
- HTTP session creation with caching
- Resource cleanup

### 2. Optional DI Adoption

- **Zero breaking changes**: Existing code continues working
- **Gradual migration**: Adopt DI at your own pace
- **Backward compatibility**: All CLI commands work without changes

### 3. 4-Phase Implementation

| Phase | Focus | Duration | Deliverables |
|-------|-------|----------|--------------|
| **Phase 1** | ServiceContainer implementation | 3-5 days | `container.py`, basic tests |
| **Phase 2** | CLI integration | 5-7 days | Updated CLI commands |
| **Phase 3** | Core module migration | 7-10 days | DI in tdocs/, specs/, meetings/ |
| **Phase 4** | Advanced DI (optional) | 5-7 days | Protocols, configuration, plugins |

## Getting Started

### For Project Architects

1. **Review the analysis** (to be created in `analysis/` directory):

   - Current dependency patterns
   - DI opportunities identified
   - Technical constraints

1. **Examine the design** (to be created in `design/` directory):

   - ServiceContainer design
   - DatabaseFactory protocol
   - HttpClientProvider abstraction
   - Migration strategy

1. **Evaluate the roadmap** (to be created in `roadmap/` directory):

   - Phase deliverables and timelines
   - Risk assessment
   - Success criteria

### For Developers

1. **Understand the ServiceContainer API**:

   ```python
   from tdoc_crawler.container import ServiceContainer

   # Create container (optional cache directory)
   container = ServiceContainer()

   # Use services
   session = container.get_session()
   with container.get_tdoc_db() as db:
       # Business logic
       pass
       
   # Cleanup
   container.close()
   ```

1. **Learn optional DI pattern**:

   ```python
   # Existing code continues working
   from tdoc_crawler.database import TDocDatabase
   from tdoc_crawler.config import CacheManager

   manager = CacheManager().register()
   with TDocDatabase(manager.db_file) as db:
       # Works as before
       pass
       
   # New code can use container
   def process_tdocs(container: ServiceContainer | None = None):
       if container is None:
           container = ServiceContainer()
       # Use container services
   ```

1. **Prepare for testing**:

   ```python
   # Mock container for testing
   class MockServiceContainer:
       def __init__(self):
           self.mock_session = MockSession()
           self.mock_db = MockTDocDatabase()
           
       def get_session(self):
           return self.mock_session
           
       def get_tdoc_db(self):
           return self.mock_db
   ```

### For Testers

1. **Review test strategy** in `plan.md`:

   - Protocol-based testing
   - Mock container patterns
   - Performance testing requirements

1. **Examine validation criteria** in `spec.md`:

   - Success criteria (SC-001 to SC-004)
   - Acceptance scenarios
   - Edge cases

1. **Prepare test cases**:

   - Container creation and lifecycle
   - Service access and caching
   - Error conditions and recovery
   - Backward compatibility verification

## Next Steps

### Immediate Actions (Week 1)

1. **Stakeholder review** of planning documents
1. **Architecture approval** of ServiceContainer design
1. **Resource allocation** for Phase 1 implementation
1. **Risk assessment** validation

### Implementation Preparation

1. **Set up development environment**:

   ```bash
   # Clone repository
   git clone https://forge.3gpp.org/rep/reimes/tdoc-crawler.git
   cd tdoc-crawler

   # Checkout feature branch
   git checkout 001-di-refactoring-plan

   # Set up Python environment
   uv sync
   ```

1. **Review existing code patterns**:

   ```bash
   # Examine current dependency patterns
   grep -r "CacheManager(" src/tdoc_crawler/
   grep -r "TDocDatabase(" src/tdoc_crawler/
   grep -r "create_cached_session" src/tdoc_crawler/
   ```

1. **Prepare test infrastructure**:

   ```bash
   # Run existing tests
   uv run pytest tests/ -v

   # Check test coverage
   uv run pytest tests/ --cov=src/tdoc_crawler --cov-report=html
   ```

## Common Questions

### Q: Will this break existing code?

**A**: No. The DI implementation is optional with backward compatibility. Existing code continues working without changes.

### Q: What's the performance impact?

**A**: Target is \<5% overhead in hot paths. Lazy loading and caching minimize impact.

### Q: How long will implementation take?

**A**: 4 phases over 2-3 weeks, depending on team size and priorities.

### Q: Do we need to learn a DI framework?

**A**: No. The implementation uses simple Python classes and protocols, no external frameworks.

### Q: How do we migrate existing code?

**A**: Gradual migration following the 4-phase roadmap. Each phase has clear deliverables and can be validated independently.

## Support & Resources

### Documentation

- **AGENTS.md**: Project guidelines and coding standards
- **README.md**: Project overview and setup
- **docs/**: User and developer documentation

### Code Examples

- **tests/**: Test examples using DI patterns
- **src/tdoc_crawler/cli/**: CLI command patterns
- **src/tdoc_crawler/tdocs/**: Domain operation patterns

### Contact Points

- **Project Lead**: Architecture decisions and approval
- **Senior Developers**: Technical review and implementation
- **Test Team**: Validation and quality assurance

## Feedback & Contributions

1. **Review the planning documents** and provide feedback
1. **Identify gaps or concerns** in the approach
1. **Suggest improvements** based on your expertise
1. **Participate in implementation** according to the roadmap

The planning is designed to be collaborative and iterative. Your input is valuable for ensuring a successful DI refactoring.

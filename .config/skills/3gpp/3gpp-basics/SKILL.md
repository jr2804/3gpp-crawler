______________________________________________________________________

## name: 3gpp-basics description: General 3GPP organization overview, partnerships, scope, and fundamental concepts. Use when working with 3GPP data structures, understanding 3GPP hierarchy, or needing context about 3GPP as an organization. metadata: related: [3gpp-working-groups, 3gpp-meetings, 3gpp-tdocs, 3gpp-portal-authentication]

# 3GPP Basics

## Overview

3GPP (3rd Generation Partnership Project) is a collaboration between seven telecommunications standard development organizations (Organizational Partners) providing their members with a stable environment to produce Reports and Specifications that define 3GPP technologies.

## Organizational Partners

The seven Organizational Partners are:

- **ARIB** (Association of Radio Industries and Businesses)
- **ATIS** (Alliance for Telecommunications Industry Solutions)
- **CCSA** (China Communications Standards Association)
- **ETSI** (European Telecommunications Standards Institute)
- **TSDSI** (Telecommunications Standards Association of India)
- **TTA** (Telecommunications Technology Association)
- **TTC** (Telecommunication Technology Committee)

## Technical Administration

Since 3GPP is not a legal entity, technical administration and infrastructure is provided by ETSI. This includes:

- Meeting information and registration: <https://portal.etsi.org/Meetings.aspx#/>
- Portal access for certain resources
- File servers and infrastructure

### MCC (Mobile Competence Centre)

The MCC is the technical support team for 3GPP operations:

- Maintains 3GPP specifications and FTP servers
- Publishes new/revised specs after each TSG round
- Manages the CR database and work item tracking
- Provides meeting document templates
- Target: specs available within 3-4 weeks after TSG plenary

### PCG (Project Coordination Group)

The PCG coordinates the 3GPP partnership:

- Coordinates work across the three TSGs
- Manages relationships with Organizational Partners
- Oversees 3GPP budget and resources
- Strategic planning for 3GPP direction

## Technical Specification Groups (TSGs)

3GPP has three main Technical Specification Groups (TSGs):

### TSG RAN (Radio Access Network)

- **Focus**: Radio aspects of mobile communications
- **Responsibilities**: Radio access technologies like LTE and 5G NR
- **FTP Root**: `https://www.3gpp.org/ftp/tsg_ran/`

### TSG SA (Service and System Aspects)

- **Focus**: Overall architecture and service aspects
- **Responsibilities**: Core network functionalities, service requirements
- **FTP Root**: `https://www.3gpp.org/ftp/tsg_sa/`

### TSG CT (Core Network and Terminals)

- **Focus**: Core network and terminal aspects
- **Responsibilities**: Protocols, interfaces between core network and user equipment
- **FTP Root**: `https://www.3gpp.org/ftp/tsg_ct/`

## Scope

3GPP specifications cover cellular telecommunications technologies, including:

- Radio access
- Core network
- Service capabilities
- Hooks for non-radio access to core network
- Interworking with non-3GPP networks

## Specifications and Work

3GPP specifications and studies (TRs) are contribution-driven by member companies in Working Groups and at Technical Specification Group (TSG) level.

The Working Groups within TSGs meet regularly and come together for their quarterly TSG Plenary meetings, where their work is presented for information, discussion, and approval.

## Releases and Generational Approach

3GPP technologies evolve through generations of commercial cellular/mobile systems. While "generations" (3G, 4G, 5G) serve as adequate descriptors for the type of network under discussion, real progress is measured by achievements in particular **Releases**.

### Key Release Concepts

- **Release Freeze**: New features are "functionally frozen" when a Release is completed
- **Backward Compatibility**: Major focus is to ensure systems are backwards and forwards compatible where possible
- **Parallel Development**: 3GPP works on multiple Releases in parallel, starting future work well in advance
- **Current Releases**: Release 20 (current), Release 19, Release 18, etc. down to Release 1999

### Example: Dual Connectivity for 5G

Many operators use dual connectivity between LTE and 5G NR equipment, using "Non-Standalone" work completed early in Release 15. Forward compatibility was built into Non-Standalone NR equipment to ensure it works on Standalone 5G NR systems.

## TDocs (Temporary Documents)

TDocs are meeting documents produced by members participating in 3GPP Working Groups and Sub-Working Groups. They include:

- Proposals for new features
- Reports on technical work
- Other documents related to standard development

Every TDoc is always allocated to a specific 3GPP meeting.

## Portal Authentication

To access certain 3GPP resources, you need an ETSI Online Account (EOL). However:

- Files on the 3GPP FTP/HTTP server are publicly accessible
- For parsing metadata or accessing certain webpages, login may be required

## See Also

- **@3gpp-working-groups** - Detailed information about Working Groups, Sub-Working Groups, tbid/SubTB identifiers
- **@3gpp-meetings** - Meeting structure, naming conventions, and web pages
- **@3gpp-tdocs** - TDoc patterns, metadata, and file server access
- **@3gpp-portal-authentication** - EOL authentication, AJAX login patterns

## Resources

- 3GPP Official Website: <https://www.3gpp.org/>
- 3GPP Work Plan: <https://www.3gpp.org/specifications-technologies/3gpp-work-plan/>
- 3GPP Portal: <https://portal.3gpp.org/>
- ETSI Portal: <https://portal.etsi.org/>

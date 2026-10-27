# AML graph investigation

Terms for evidence-backed investigation of the synthetic transaction network.

## Language

**Account**:
A bank-and-account pair identifying one transaction endpoint. The same account number at two banks denotes two different accounts.
_Avoid_: Account number as a complete identity

**Transaction edge**:
One original transaction record connecting its source account to its destination account. Similar or identical-looking records remain distinct edges.
_Avoid_: Deduplicated payment

**Return cycle**:
A directed sequence of external transaction edges returning to its starting account. A simple return cycle has no repeated internal account.
_Avoid_: Proof of laundering

**Temporal cycle**:
A return cycle whose edges follow strictly increasing recorded timestamps. Equal-minute timestamps do not establish the required ordering.
_Avoid_: Time-ordered cycle inferred from row order

**Reference episode**:
A group of transactions identified together in the publisher's answer material. Its membership does not guarantee that it satisfies a particular investigation rule.
_Avoid_: Detected case

**Candidate case**:
An evidence-backed observation proposed for assessment or human follow-up. It distinguishes the observed pattern from any hypothesis about its purpose.
_Avoid_: Confirmed laundering

**Source prevalence**:
The proportion of transactions carrying a specified label or family membership within a declared source population.
_Avoid_: Case prevalence when counting transactions

**Supporting evidence**:
Transactions and contextual facts relevant to a candidate case. Being shown as context does not automatically implicate a transaction.
_Avoid_: All reviewed rows as suspicious rows

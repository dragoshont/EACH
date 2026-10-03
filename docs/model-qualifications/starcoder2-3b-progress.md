# StarCoder2-3B lineage assessment

Status, 2026-10-03: **BLOCKED pending supplementary/synthetic-data lineage
assessment.** Model and training-ID access are granted. Access alone is not
eligibility, and the model has not been loaded or evaluated through EACH.

Candidate: `bigcode/starcoder2-3b` at
`733247c55e3f73af49ce8e9c7949bf14af205928`.

## Use the size-specific recipe, not the generic model-card wording

The original paper's section 4 and table 4 specify that the **3B** model uses:

- The Stack v2 small repository-context subset (17 programming languages
  plus selected configuration/documentation languages).
- Pull requests, issues, structured/script Jupyter notebooks, Kaggle scripts,
  library documentation, StackOverflow, the LHQ mixture and intermediate
  representations.
- **Not** OpenWebMath, Wikipedia or arXiv. Those appear in the family-wide
  documentation and larger-model mixtures, not the table's 3B selection.

The 16K-context checkpoint also received **200B tokens of continued
pretraining from the same pretraining corpus** after the 4K-context stage.
This is a real additional training stage; calling it a base model does not
erase it.

Primary evidence: [StarCoder2 paper](https://arxiv.org/html/2402.19173v1),
sections 2, 4 and 6, tables 4 and 8.

## Access and released sources

The authenticated Mac can access the actual training-ID shard at
`bigcode/the-stack-v2-train-smol-ids@d54939b9c178ca392f68fae3612ab20c15c673ac`.
These are source identifiers, not bulk code contents. The dataset changelog
distinguishes the v2.0.1 training release from subsequent opt-out updates.
Current IDs must not be silently treated as the unchanged historical mixture.

The paper's logical name `the-stack-v2-train-extras` did not resolve as a
dataset repository. The actual released repository is
`bigcode/starcoder2data-extras@1ba0d4f31e4c3b6d8586505669841432a19b8c16`;
its metadata and an actual parquet file HEAD are accessible. Its card names
the supplementary sources and schemas. This resolves a naming/access
confusion, not full source-stage qualification.

Preprocessing source:
`bigcode-project/the-stack-v2@917204185fa014813d03020532e7ef9078609c4d`.
Its PR pipeline README identifies auxiliary repository-license and commit-pair
inputs and says some inputs were to be released later. Confidential opt-out
lists are not themselves model training data, but exact processed PR/notebook
release identities still need mapping.

## Specific unresolved synthetic ancestry

The 3B LHQ mixture includes GSM8K-SciRel and MultiPL-T as well as
APPS, CodeContests, GSM8K-train, DeepMind Mathematics, Rosetta Code and proof
datasets. Publicly released synthetic outputs do not automatically establish
clear generator training lineage.

- MultiPL-T's source guide identifies **StarCoderBase-15B** translation and
  LLM-generated tests, with execution filtering. That is a traceable candidate
  ancestry, but the exact included release and test-generation stage still
  require assessment.
- GSM8K-SciRel's cited paper describes rejection-sampled reasoning generated
  by supervised **LLaMA/LLaMA2-family models**. Their training-data lineage has
  not been qualified here. The exact synthetic subset included in this model
  has not been mapped. This is not waived merely because generated examples
  are readable or answers pass a correctness filter.
- The StackOverflow preprocessing uses Llama-2-70B-chat ratings to train a
  filter. Filtering labels and generated training answers are distinct roles;
  assess what enters the final data rather than claiming either automatic
  contamination or automatic clearance.

Until these questions are resolved under the same required base/post/synthetic
lineage policy, keep this candidate blocked and continue the independently
qualified candidates. No extra model or training-corpus content has been
downloaded for inference, no gated terms accepted by the assistant and no
StarCoder2 target generation performed.

## Independent decision

A separate Adversarial Judge reviewed this dossier against the accepted
StarCoderBase/OctoCoder standard and returned **BLOCKED / REVISE**. It inspected
repository documents, not authenticated requests or the linked public papers
independently; those source checks remain coordinator-collected evidence.
This is a bounded eligibility assessment, not a cross-family release gate.

The decisive unresolved question is the ancestry of intentional synthetic
reasoning, not a demand to reconstruct every sampled row or prove every
record lawful. Mapping all potentially included generator populations to
qualified ancestors can suffice without exact row membership. If only some
generators qualify, subset evidence must distinguish them. Merely excluding
a problematic dataset from a new description, or fine-tuning these weights
again, cannot remove that ancestry from the existing checkpoint.

## Remaining acceptance evidence

1. Map the historical training-ID release and actual code-content access.
2. Map each included supplementary source/revision, especially PR/notebook
   representations and the LHQ sub-mixtures.
3. Resolve synthetic-generator ancestry, with required unknowns blocking.
4. Independently review the complete dossier before enabling the loader.

Sources:
- [Size-specific original paper](https://arxiv.org/html/2402.19173v1)
- [Supplementary dataset card](https://huggingface.co/datasets/bigcode/starcoder2data-extras/blob/1ba0d4f31e4c3b6d8586505669841432a19b8c16/README.md)
- [Training-ID dataset](https://huggingface.co/datasets/bigcode/the-stack-v2-train-smol-ids)
- [Pinned PR preprocessing notes](https://github.com/bigcode-project/the-stack-v2/blob/917204185fa014813d03020532e7ef9078609c4d/pull_requests_and_issues/README.md)
- [MultiPL-T source guide](https://github.com/nuprl/MultiPL-T)
- [GSM8K-SciRel source paper](https://arxiv.org/html/2308.01825v2)

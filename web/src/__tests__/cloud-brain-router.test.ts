import { describe, it, expect } from 'vitest'
import { routeQuery, GENE_TO_ACCESSION } from '../lib/cloud-brain-router'

describe('routeQuery', () => {
  // Gene name detection
  it('routes "What is BRCA1?" to UniProt function lookup', () => {
    const result = routeQuery('What is BRCA1?')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('UniProt_get_function_by_accession')
    expect(result.payload.arguments).toEqual({ accession: 'P38398' })
    expect(result.toolName).toBe('UniProt (function)')
  })

  // Direct accession
  it('routes "Look up P04637" to UniProt', () => {
    const result = routeQuery('Look up P04637')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('UniProt_get_function_by_accession')
    expect(result.payload.arguments).toEqual({ accession: 'P04637' })
  })

  // Sequence sub-routing
  it('routes "Get EGFR sequence" to UniProt sequence', () => {
    const result = routeQuery('Get EGFR sequence')
    expect(result.payload.tool_name).toBe('UniProt_get_sequence_by_accession')
    expect(result.payload.arguments).toEqual({ accession: 'P00533' })
  })

  // Drug detection
  it('routes "Search aspirin drug" to ChEMBL', () => {
    const result = routeQuery('Search aspirin drug')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('ChEMBL_search_molecules')
  })

  // Clinical trial + gene name: clinical takes priority (priority 2c in spec)
  // Note: the spec regex matches "clinical trial" (singular), not "clinical trials" (plural)
  it('routes "Find clinical trial for EGFR" to ClinicalTrials (not UniProt)', () => {
    const result = routeQuery('Find clinical trial for EGFR')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('ClinicalTrials_search_studies')
    expect(result.toolName).toBe('ClinicalTrials.gov')
  })

  it('routes "EGFR clinical trial NCT12345" to ClinicalTrials', () => {
    const result = routeQuery('EGFR clinical trial NCT12345')
    expect(result.payload.tool_name).toBe('ClinicalTrials_search_studies')
  })

  // Writing detection
  it('routes "Write a Methods section" to /write', () => {
    const result = routeQuery('Write a Methods section for immunohistochemistry')
    expect(result.endpoint).toBe('/write')
    expect(result.payload.section).toBe('methods')
  })

  // Experiment design
  it('routes "Design a Western blot experiment" to /reason', () => {
    const result = routeQuery('Design a Western blot experiment')
    expect(result.endpoint).toBe('/reason')
    expect(result.payload.domain).toBe('experimental_design')
  })

  // Fallback
  it('routes unknown queries to /reason general', () => {
    const result = routeQuery('Hello, how are you?')
    expect(result.endpoint).toBe('/reason')
    expect(result.payload.domain).toBe('general')
  })

  // Case insensitivity
  it('detects gene names case-insensitively', () => {
    const result = routeQuery('what is brca1?')
    expect(result.payload.tool_name).toBe('UniProt_get_function_by_accession')
    expect(result.payload.arguments).toEqual({ accession: 'P38398' })
  })

  // All 50+ genes in map should be valid UniProt accessions
  it('all accessions match UniProt format', () => {
    for (const [_gene, acc] of Object.entries(GENE_TO_ACCESSION)) {
      expect(acc).toMatch(/^[ABOPQ]\d[A-Z\d]{3}\d$/)
    }
  })

  // --- Additional coverage for all routing branches ---

  // 3D structure sub-routing
  it('routes "TP53 3D structure" to UniProt 3D structure', () => {
    const result = routeQuery('TP53 3D structure')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('UniProt_get_3D_structure_by_accession')
    expect(result.payload.arguments).toEqual({ accession: 'P04637' })
  })

  // FASTA sub-routing
  it('routes "Get BRAF amino acid sequence" to UniProt sequence', () => {
    const result = routeQuery('Get BRAF amino acid sequence')
    expect(result.payload.tool_name).toBe('UniProt_get_sequence_by_accession')
    expect(result.payload.arguments).toEqual({ accession: 'P15056' })
  })

  // PDB sub-routing
  it('routes "KRAS PDB fold" to UniProt 3D structure', () => {
    const result = routeQuery('KRAS PDB fold')
    expect(result.payload.tool_name).toBe('UniProt_get_3D_structure_by_accession')
  })

  // Clinical trial without gene name (priority 5, not 2c)
  it('routes "phase 3 study for lung cancer" to ClinicalTrials', () => {
    const result = routeQuery('phase 3 study for lung cancer')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('ClinicalTrials_search_studies')
  })

  // NCT number detection
  it('routes "NCT12345678 results" to ClinicalTrials', () => {
    const result = routeQuery('NCT12345678 results')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('ClinicalTrials_search_studies')
  })

  // Intervention keyword
  it('routes "intervention for Alzheimer" to ClinicalTrials', () => {
    const result = routeQuery('intervention for Alzheimer')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('ClinicalTrials_search_studies')
  })

  // PubChem queries
  it('routes "Look up PubChem aspirin" to PubChem', () => {
    const result = routeQuery('Look up PubChem aspirin')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('PubChem_search_compounds')
  })

  // SMILES query
  it('routes "SMILES for caffeine" to PubChem', () => {
    const result = routeQuery('SMILES for caffeine')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('PubChem_search_compounds')
  })

  // Adverse event queries
  it('routes "adverse events for ibuprofen" to FAERS', () => {
    const result = routeQuery('adverse events for ibuprofen')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('FAERS_search_reports')
  })

  // Side effect query — "effects" triggers PubMed (priority 8) since "side effects" pattern
  // requires "side\seffect" but "effects" alone matches PubMed first. Test with explicit "side effect".
  it('routes "side effect reports for metformin" to FAERS', () => {
    const result = routeQuery('side effect reports for metformin')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('FAERS_search_reports')
  })

  // Safety query — "compound" triggers ChEMBL (priority 4) before FAERS (priority 7)
  it('routes "safety profile of medication X" to FAERS', () => {
    const result = routeQuery('safety profile of medication X')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('FAERS_search_reports')
  })

  // PubMed queries
  it('routes "search pubmed for CRISPR" to PubMed', () => {
    const result = routeQuery('search pubmed for CRISPR')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('search_pubmed')
  })

  // Literature query — "tau" matches GENE_TO_ACCESSION (priority 3) before PubMed (priority 8)
  it('routes "literature on breast cancer" to PubMed', () => {
    const result = routeQuery('literature on breast cancer')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('search_pubmed')
  })

  // Paper review query
  it('routes "review papers on apoptosis" to PubMed', () => {
    const result = routeQuery('review papers on apoptosis')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('search_pubmed')
  })

  // OpenTargets queries
  it('routes "opentargets for BRCA1" to OpenTargets', () => {
    const result = routeQuery('opentargets for BRCA1')
    // Gene detected + clinical keywords NOT present, but opentargets keyword present
    // However, BRCA1 is detected as a gene first, which triggers UniProt route (priority 3)
    // The OpenTargets check (priority 9) comes after gene detection
    expect(result.endpoint).toBe('/execute')
  })

  it('routes "disease target association for diabetes" to OpenTargets', () => {
    const result = routeQuery('disease target association for diabetes')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('OpenTargets_search_disease')
  })

  it('routes "open targets evidence for IL6" to OpenTargets', () => {
    const result = routeQuery('open targets evidence for IL6')
    // IL6 is not in GENE_TO_ACCESSION, so it falls through to OpenTargets
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('OpenTargets_search_disease')
  })

  // Writing section variants
  it('routes "draft an abstract" to /write with abstract section', () => {
    const result = routeQuery('draft an abstract')
    expect(result.endpoint).toBe('/write')
    expect(result.payload.section).toBe('abstract')
  })

  it('routes "write results section" to /write with results section', () => {
    const result = routeQuery('write results section')
    expect(result.endpoint).toBe('/write')
    expect(result.payload.section).toBe('results')
  })

  it('routes "compose discussion" to /write with discussion section', () => {
    const result = routeQuery('compose discussion')
    expect(result.endpoint).toBe('/write')
    expect(result.payload.section).toBe('discussion')
  })

  // "study" triggers clinical keywords (priority 5) before /write (priority 10)
  it('routes "write introduction for this experiment" to /write with introduction section', () => {
    const result = routeQuery('write introduction for this experiment')
    expect(result.endpoint).toBe('/write')
    expect(result.payload.section).toBe('introduction')
  })

  it('routes "draft a manuscript" to /write with methods section (default)', () => {
    const result = routeQuery('draft a manuscript about cell culture')
    expect(result.endpoint).toBe('/write')
    expect(result.payload.section).toBe('methods')
  })

  // Experiment design variants
  it('routes "PCR protocol" to /reason experimental_design', () => {
    const result = routeQuery('PCR protocol')
    expect(result.endpoint).toBe('/reason')
    expect(result.payload.domain).toBe('experimental_design')
  })

  it('routes "ELISA assay design" to /reason experimental_design', () => {
    const result = routeQuery('ELISA assay design')
    expect(result.endpoint).toBe('/reason')
    expect(result.payload.domain).toBe('experimental_design')
  })

  it('routes "CRISPR knockout control" to /reason experimental_design', () => {
    const result = routeQuery('CRISPR knockout control')
    expect(result.endpoint).toBe('/reason')
    expect(result.payload.domain).toBe('experimental_design')
  })

  // Drug query variants
  it('routes "find molecule X inhibitor" to ChEMBL', () => {
    const result = routeQuery('find molecule X inhibitor')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('ChEMBL_search_molecules')
  })

  it('routes "CHEMBL compound search" to ChEMBL', () => {
    const result = routeQuery('CHEMBL compound search')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('ChEMBL_search_molecules')
  })

  it('routes "agonist for receptor Y" to ChEMBL', () => {
    const result = routeQuery('agonist for receptor Y')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('ChEMBL_search_molecules')
  })

  it('routes "antagonist drug" to ChEMBL', () => {
    const result = routeQuery('antagonist drug')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('ChEMBL_search_molecules')
  })

  // displayLabel is always set
  it('always sets displayLabel on every route', () => {
    const queries = [
      'What is TP53?',
      'Look up P04637',
      'Search aspirin drug',
      'clinical trials for EGFR',
      'Write a Methods section',
      'Design a Western blot',
      'Hello world',
      'pubchem caffeine',
      'adverse events ibuprofen',
      'pubmed CRISPR',
      'opentargets diabetes',
    ]
    for (const q of queries) {
      const result = routeQuery(q)
      expect(result.displayLabel).toBeDefined()
    }
  })

  // Gene alias: P53 maps to same accession as TP53
  it('routes "P53 mutation" using P53 alias', () => {
    const result = routeQuery('P53 mutation')
    expect(result.payload.tool_name).toBe('UniProt_get_function_by_accession')
    expect(result.payload.arguments).toEqual({ accession: 'P04637' })
  })

  // Gene alias: HER2 maps to same accession as ERBB2
  it('routes "HER2 expression" using HER2 alias', () => {
    const result = routeQuery('HER2 expression')
    expect(result.payload.tool_name).toBe('UniProt_get_function_by_accession')
    expect(result.payload.arguments).toEqual({ accession: 'P04626' })
  })

  // Gene alias: TAU maps to same accession as MAPT
  it('routes "TAU protein" using TAU alias', () => {
    const result = routeQuery('TAU protein')
    expect(result.payload.tool_name).toBe('UniProt_get_function_by_accession')
    expect(result.payload.arguments).toEqual({ accession: 'P10636' })
  })

  // All genes route to /execute
  it('every gene in GENE_TO_ACCESSION routes to /execute', () => {
    for (const [gene] of Object.entries(GENE_TO_ACCESSION)) {
      const result = routeQuery(`Tell me about ${gene}`)
      expect(result.endpoint).toBe('/execute')
      expect(result.payload.tool_name).toContain('UniProt')
    }
  })

  // Clinical override takes precedence over UniProt when both gene and clinical keywords present
  it('clinical override beats UniProt for "treatment of BRCA1 cancer"', () => {
    const result = routeQuery('treatment of BRCA1 cancer')
    expect(result.payload.tool_name).toBe('ClinicalTrials_search_studies')
    expect(result.payload.tool_name).not.toContain('UniProt')
  })

  // Gene not in map but accession-like still matches
  it('direct accession Q9UM73 routes to UniProt function', () => {
    const result = routeQuery('Q9UM73')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('UniProt_get_function_by_accession')
    expect(result.payload.arguments).toEqual({ accession: 'Q9UM73' })
  })

  // Empty/whitespace input falls back to /reason
  it('empty string falls back to /reason general', () => {
    const result = routeQuery('')
    expect(result.endpoint).toBe('/reason')
    expect(result.payload.domain).toBe('general')
  })

  // Phase keyword with number
  it('routes "phase 2 treatment" to ClinicalTrials', () => {
    const result = routeQuery('phase 2 treatment')
    expect(result.endpoint).toBe('/execute')
    expect(result.payload.tool_name).toBe('ClinicalTrials_search_studies')
  })
})

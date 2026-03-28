/**
 * Cloud Brain NLP Router — maps natural language queries to backend endpoints.
 * Spec: docs/specs/2026-03-26-cloud-brain-upgrade-design.md Section 5
 */

export interface RouteResult {
  endpoint: '/execute' | '/reason' | '/write'
  payload: Record<string, unknown>
  toolName?: string
  toolArgs?: Record<string, unknown>
  displayLabel?: string
}

export const GENE_TO_ACCESSION: Record<string, string> = {
  // Tumor suppressors & oncogenes
  BRCA1: 'P38398',  BRCA2: 'P51587',
  TP53: 'P04637',   P53: 'P04637',
  EGFR: 'P00533',   HER2: 'P04626',  ERBB2: 'P04626',
  KRAS: 'P01116',   BRAF: 'P15056',
  MYC: 'P01106',    RB1: 'P06400',
  PTEN: 'P60484',   APC: 'P25054',
  VHL: 'P40337',    RAS: 'P01112',

  // Kinases & signaling
  AKT1: 'P31749',   MTOR: 'P42345',
  PIK3CA: 'P42336', JAK2: 'O60674',
  SRC: 'P12931',    ABL1: 'P00519',
  CDK4: 'P11802',   CDK6: 'Q00534',
  RAF1: 'P04049',   MEK1: 'Q02750',
  ERK2: 'P28482',   MAP2K1: 'Q02750',

  // DNA repair & chromatin
  ATM: 'Q13315',    ATR: 'Q13535',
  CHEK1: 'O14757',  CHEK2: 'O96017',
  PALB2: 'Q86YC2',  RAD51: 'Q06609',

  // Growth factors & receptors
  VEGFA: 'P15692',  PDGFRA: 'P16234',
  FGFR1: 'P11362',  FGFR2: 'P21802',
  KIT: 'P10721',    MET: 'P08581',
  ALK: 'Q9UM73',    RET: 'P07949',
  ROS1: 'P08922',   NTRK1: 'P04629',
  IGF1R: 'P08069',  INSR: 'P06213',

  // Immune / checkpoint
  PD1: 'Q15116',    PDL1: 'Q9NZQ7',
  CTLA4: 'P16410',  CD19: 'P15391',
  CD20: 'P11836',

  // Metabolic enzymes
  IDH1: 'O75874',   IDH2: 'P48735',

  // Neuroscience
  APP: 'P05067',     MAPT: 'P10636',  TAU: 'P10636',
  APOE: 'P02649',   SNCA: 'P37840',
  HTT: 'P42858',    SOD1: 'P00441',
  BDNF: 'P23560',   GRIN1: 'Q05586',
}

// UniProt accession pattern: e.g. P04637, Q9NZQ7
const ACCESSION_RE = /\b([ABOPQ]\d[A-Z\d]{3}\d)\b/i

export function routeQuery(input: string): RouteResult {
  const q = input.trim()

  // 1. Direct UniProt accession in query
  const accessionMatch = q.match(ACCESSION_RE)

  // 2. Gene name detection
  let detectedAccession: string | undefined
  let detectedGene: string | undefined
  for (const [gene, acc] of Object.entries(GENE_TO_ACCESSION)) {
    // Match whole word (case-insensitive)
    const re = new RegExp(`\\b${gene}\\b`, 'i')
    if (re.test(q)) {
      detectedAccession = acc
      detectedGene = gene
      break
    }
  }

  const accession = accessionMatch?.[1] ?? detectedAccession

  // 2b. Clinical keywords detection
  const hasClinicalKeywords = /\b(clinical\s*trial|study|treatment|phase\s*[1-4]|nct\d+|intervention)\b/i.test(q)

  // 2c. Priority override: clinical keywords + gene = clinical route
  if (hasClinicalKeywords && detectedGene) {
    const searchTerm = q
      .replace(/\b(search|find|look\s*up|clinical|trial|trials|study|studies)\b/gi, '')
      .trim() || q
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'ClinicalTrials_search_studies',
        arguments: { query: searchTerm },
      },
      toolName: 'ClinicalTrials.gov',
      toolArgs: { query: searchTerm },
      displayLabel: 'ClinicalTrials.gov',
    }
  }

  // 3. If accession found, decide which UniProt tool
  if (accession) {
    if (/sequence|amino\s*acid|fasta/i.test(q)) {
      return {
        endpoint: '/execute',
        payload: {
          tool_name: 'UniProt_get_sequence_by_accession',
          arguments: { accession },
        },
        toolName: 'UniProt (sequence)',
        toolArgs: { accession, gene: detectedGene },
        displayLabel: 'UniProt (sequence)',
      }
    }
    if (/structure|3d|pdb|fold/i.test(q)) {
      return {
        endpoint: '/execute',
        payload: {
          tool_name: 'UniProt_get_3D_structure_by_accession',
          arguments: { accession },
        },
        toolName: 'UniProt (3D structure)',
        toolArgs: { accession, gene: detectedGene },
        displayLabel: 'UniProt (3D structure)',
      }
    }
    // Default for gene/protein queries: get function
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'UniProt_get_function_by_accession',
        arguments: { accession },
      },
      toolName: 'UniProt (function)',
      toolArgs: { accession, gene: detectedGene },
      displayLabel: 'UniProt (function)',
    }
  }

  // 4. Drug / molecule queries
  if (/\b(drug|molecule|chembl|compound|inhibitor|agonist|antagonist)\b/i.test(q)) {
    // Extract the search term: remove the keyword, take remaining meaningful words
    const searchTerm = q
      .replace(/\b(search|find|look\s*up|query|what|is|the|for|about|info|information|drug|molecule|compound)\b/gi, '')
      .trim() || q
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'ChEMBL_search_molecules',
        arguments: { query: searchTerm },
      },
      toolName: 'ChEMBL (molecule search)',
      toolArgs: { query: searchTerm },
      displayLabel: 'ChEMBL (molecule search)',
    }
  }

  // 5. Clinical trial queries (reuse hasClinicalKeywords from 2b)
  if (hasClinicalKeywords) {
    const searchTerm = q
      .replace(/\b(search|find|look\s*up|clinical|trial|trials|study|studies)\b/gi, '')
      .trim() || q
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'ClinicalTrials_search_studies',
        arguments: { query: searchTerm },
      },
      toolName: 'ClinicalTrials.gov',
      toolArgs: { query: searchTerm },
      displayLabel: 'ClinicalTrials.gov',
    }
  }

  // 6. PubChem queries
  if (/\b(pubchem|chemical|cas\s*number|smiles|inchi)\b/i.test(q)) {
    const searchTerm = q
      .replace(/\b(search|find|look\s*up|pubchem|chemical)\b/gi, '')
      .trim() || q
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'PubChem_search_compounds',
        arguments: { query: searchTerm },
      },
      toolName: 'PubChem',
      toolArgs: { query: searchTerm },
      displayLabel: 'PubChem',
    }
  }

  // 7. Adverse event queries
  if (/\b(adverse|side\s*effect|faers|safety|toxicity)\b/i.test(q)) {
    const searchTerm = q
      .replace(/\b(search|find|look\s*up|adverse|event|events|side|effect|effects|report|reports)\b/gi, '')
      .trim() || q
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'FAERS_search_reports',
        arguments: { query: searchTerm },
      },
      toolName: 'FAERS (adverse events)',
      toolArgs: { query: searchTerm },
      displayLabel: 'FAERS (adverse events)',
    }
  }

  // 8. PubMed / literature queries
  if (/\b(pubmed|literature|papers?|review|citation|search\s*papers)\b/i.test(q)) {
    const searchTerm = q
      .replace(/\b(search|find|look\s*up|pubmed|literature|papers?|review|citation)\b/gi, '')
      .trim() || q
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'search_pubmed',
        arguments: { query: searchTerm },
      },
      toolName: 'PubMed',
      toolArgs: { query: searchTerm },
      displayLabel: 'PubMed',
    }
  }

  // 9. OpenTargets / disease-target queries
  if (/\b(opentargets|open\s*targets|evidence|association|disease\s*target)\b/i.test(q)) {
    const searchTerm = q
      .replace(/\b(search|find|look\s*up|opentargets|open\s*targets|evidence|association)\b/gi, '')
      .trim() || q
    return {
      endpoint: '/execute',
      payload: {
        tool_name: 'OpenTargets_search_disease',
        arguments: { query: searchTerm },
      },
      toolName: 'OpenTargets',
      toolArgs: { query: searchTerm },
      displayLabel: 'OpenTargets',
    }
  }

  // 10. Scientific writing
  if (/\b(write|draft|compose|abstract|methods?\s*section|results?\s*section|discussion|introduction|manuscript)\b/i.test(q)) {
    // Detect section type
    let section = 'methods'
    if (/abstract/i.test(q)) section = 'abstract'
    else if (/result/i.test(q)) section = 'results'
    else if (/discussion/i.test(q)) section = 'discussion'
    else if (/introduction/i.test(q)) section = 'introduction'

    return {
      endpoint: '/write',
      payload: { section, context: q },
      toolName: `Scientific Writing (${section})`,
      displayLabel: `Scientific Writing (${section})`,
    }
  }

  // 11. Experiment design / reasoning
  if (/\b(design|experiment|protocol|assay|western\s*blot|pcr|elisa|crispr|control)\b/i.test(q)) {
    return {
      endpoint: '/reason',
      payload: { question: q, domain: 'experimental_design' },
      toolName: 'Life Science Reasoning',
      displayLabel: 'Life Science Reasoning',
    }
  }

  // 12. Fallback: general reasoning
  return {
    endpoint: '/reason',
    payload: { question: q, domain: 'general' },
    toolName: 'Cloud Brain',
    displayLabel: 'Cloud Brain',
  }
}

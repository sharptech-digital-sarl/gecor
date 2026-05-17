import LegalDocumentPage from '../components/legal/LegalDocumentPage'

const SECTIONS = [
  { titleKey: 'legal.terms.s1Title', bodyKey: 'legal.terms.s1Body' },
  { titleKey: 'legal.terms.s2Title', bodyKey: 'legal.terms.s2Body' },
  { titleKey: 'legal.terms.s3Title', bodyKey: 'legal.terms.s3Body' },
  { titleKey: 'legal.terms.s4Title', bodyKey: 'legal.terms.s4Body' },
  { titleKey: 'legal.terms.s5Title', bodyKey: 'legal.terms.s5Body' },
  { titleKey: 'legal.terms.s6Title', bodyKey: 'legal.terms.s6Body' },
  { titleKey: 'legal.terms.s7Title', bodyKey: 'legal.terms.s7Body' },
] as const

export default function TermsOfUse() {
  return (
    <LegalDocumentPage
      titleKey="legal.terms.title"
      updatedKey="legal.terms.updated"
      sections={SECTIONS}
    />
  )
}

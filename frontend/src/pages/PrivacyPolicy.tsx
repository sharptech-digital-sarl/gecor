import LegalDocumentPage from '../components/legal/LegalDocumentPage'

const SECTIONS = [
  { titleKey: 'legal.privacy.s1Title', bodyKey: 'legal.privacy.s1Body' },
  { titleKey: 'legal.privacy.s2Title', bodyKey: 'legal.privacy.s2Body' },
  { titleKey: 'legal.privacy.s3Title', bodyKey: 'legal.privacy.s3Body' },
  { titleKey: 'legal.privacy.s4Title', bodyKey: 'legal.privacy.s4Body' },
  { titleKey: 'legal.privacy.s5Title', bodyKey: 'legal.privacy.s5Body' },
  { titleKey: 'legal.privacy.s6Title', bodyKey: 'legal.privacy.s6Body' },
] as const

export default function PrivacyPolicy() {
  return (
    <LegalDocumentPage
      titleKey="legal.privacy.title"
      updatedKey="legal.privacy.updated"
      sections={SECTIONS}
    />
  )
}

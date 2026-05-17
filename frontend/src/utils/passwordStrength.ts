/** Jauge de robustesse (recommandations, alignées sur une politique type entreprise). */

export type PasswordStrengthResult = {
  score: number
  percent: number
  labelKey: 'passwordStrength.veryWeak' | 'passwordStrength.weak' | 'passwordStrength.fair' | 'passwordStrength.good' | 'passwordStrength.strong'
  color: 'error' | 'warning' | 'info' | 'success'
  rules: { key: string; ok: boolean }[]
}

export function evaluatePasswordStrength(password: string): PasswordStrengthResult {
  const rules = [
    { key: 'passwordStrength.ruleMin8', ok: password.length >= 8 },
    { key: 'passwordStrength.ruleLower', ok: /[a-z]/.test(password) },
    { key: 'passwordStrength.ruleUpper', ok: /[A-Z]/.test(password) },
    { key: 'passwordStrength.ruleDigit', ok: /\d/.test(password) },
    { key: 'passwordStrength.ruleSpecial', ok: /[^A-Za-z0-9]/.test(password) },
  ]
  const passed = rules.filter((r) => r.ok).length
  let score = 0
  if (password.length === 0) {
    score = 0
  } else if (password.length < 8) {
    score = 1
  } else {
    score = 1
    if (passed >= 3) score = 2
    if (passed >= 4) score = 3
    if (passed >= 5 && password.length >= 12) score = 4
  }

  const percent = score === 0 ? 0 : Math.min(100, (score / 4) * 100)
  const labels: PasswordStrengthResult['labelKey'][] = [
    'passwordStrength.veryWeak',
    'passwordStrength.weak',
    'passwordStrength.fair',
    'passwordStrength.good',
    'passwordStrength.strong',
  ]
  const colors: PasswordStrengthResult['color'][] = ['error', 'error', 'warning', 'info', 'success']

  return {
    score,
    percent,
    labelKey: labels[score],
    color: colors[score],
    rules,
  }
}

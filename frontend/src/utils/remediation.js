export function hasRemediationInfo(finding) {
  if (!finding || typeof finding !== 'object') return false
  return Boolean(
    finding.recommendation ||
    (Array.isArray(finding.remediation_steps) && finding.remediation_steps.length > 0) ||
    finding.sql_remediation ||
    finding.sql_recommendation ||
    finding.sql_fix ||
    finding.suggested_action,
  )
}


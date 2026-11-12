import { useState } from 'react'
import Logo from '../assets/Logo.png'
import { loginUser, registerUser } from '../api/pgguardian'
import './AuthLandingPage.css'

const EMAIL_RE = /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+$/

function isValidEmail(email) {
  const clean = email.trim().toLowerCase()
  return (
    clean.length > 0 &&
    clean.length <= 255 &&
    !clean.includes('..') &&
    EMAIL_RE.test(clean)
  )
}

function containsEmailPart(password, email) {
  if (!password) return false
  const cleanEmail = email.trim().toLowerCase()
  if (!cleanEmail) return false
  const localPart = cleanEmail.split('@')[0]
  const pwdLower = password.toLowerCase()
  return (
    (cleanEmail && pwdLower.includes(cleanEmail)) ||
    (localPart && pwdLower.includes(localPart))
  )
}

export default function AuthLandingPage({
  initialTab = 'login',
  initialError = null,
  onAuthenticated,
}) {
  const [activeTab, setActiveTab] = useState(initialTab === 'register' ? 'register' : 'login')
  const [showPasswords, setShowPasswords] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(initialError)

  // Estado de inicio de sesión
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')

  // Estado de registro
  const [regName, setRegName] = useState('')
  const [regEmail, setRegEmail] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regPasswordConfirm, setRegPasswordConfirm] = useState('')
  const [regAttempted, setRegAttempted] = useState(false)

  const trimmedRegName = regName.trim()
  const normalizedRegEmail = regEmail.trim().toLowerCase()
  const regNameOk = trimmedRegName.length > 0 && trimmedRegName.length <= 150
  const regEmailOk = isValidEmail(normalizedRegEmail)
  const hasRegPwd = regPassword.length > 0
  const regLengthOk =
    regPassword.length >= 12 &&
    regPassword.length <= 128 &&
    regPassword.trim().length > 0
  const regNoEmailOk = hasRegPwd && !containsEmailPart(regPassword, normalizedRegEmail)
  const regMatchOk = hasRegPwd && regPassword === regPasswordConfirm
  const regFormOk = regNameOk && regEmailOk && regLengthOk && regNoEmailOk && regMatchOk

  const getRuleState = (passed, active) => {
    if (!active) return 'pending'
    return passed ? 'ok' : 'error'
  }

  const regRules = [
    {
      id: 'length',
      label: `Longitud de 12 a 128 caracteres (${regPassword.length}/128)`,
      state: getRuleState(regLengthOk, hasRegPwd || regAttempted),
    },
    {
      id: 'no-email',
      label: 'No contiene tu correo electrónico ni el nombre antes de @',
      state: getRuleState(regNoEmailOk, hasRegPwd || regAttempted),
    },
    {
      id: 'match',
      label: 'La confirmación coincide exactamente con la contraseña',
      state: getRuleState(regMatchOk, regPasswordConfirm.length > 0 || regAttempted),
    },
  ]

  const switchTab = (tab) => {
    if (isSubmitting) return
    setActiveTab(tab)
    setError(null)
    setRegAttempted(false)
    setShowPasswords(false)
  }

  const handleLoginSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    const cleanEmail = loginEmail.trim().toLowerCase()
    if (!isValidEmail(cleanEmail)) {
      setError('Ingresa un correo electrónico válido.')
      return
    }
    if (!loginPassword) {
      setError('Ingresa tu contraseña para iniciar sesión.')
      return
    }

    setIsSubmitting(true)
    try {
      const data = await loginUser({ email: cleanEmail, password: loginPassword })
      onAuthenticated(data.user)
    } catch (err) {
      setError(err.message || 'No se pudo iniciar sesión.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleRegisterSubmit = async (e) => {
    e.preventDefault()
    setRegAttempted(true)
    setError(null)

    if (!regFormOk) {
      if (!regNameOk) {
        setError('Ingresa tu nombre completo.')
      } else if (!regEmailOk) {
        setError('Ingresa un correo electrónico válido.')
      } else if (!regLengthOk) {
        setError('La contraseña debe tener entre 12 y 128 caracteres y no ser solo espacios.')
      } else if (!regNoEmailOk) {
        setError('La contraseña no puede contener tu correo electrónico ni su parte local.')
      } else if (!regMatchOk) {
        setError('Las contraseñas no coinciden.')
      }
      return
    }

    setIsSubmitting(true)
    try {
      const data = await registerUser({
        name: trimmedRegName,
        email: normalizedRegEmail,
        password: regPassword,
        password_confirm: regPasswordConfirm,
      })
      onAuthenticated({ id: data.id, name: data.name, email: data.email })
    } catch (err) {
      setError(err.message || 'No se pudo completar el registro.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="auth-landing">
      <div className="auth-landing-container fade-in">
        <section className="auth-hero">
          <div className="auth-brand">
            <img src={Logo} alt="PgGuardian" className="auth-brand-logo" />
            <div>
              <span className="auth-brand-badge">Auditoría PostgreSQL</span>
              <h1 className="auth-brand-name">PgGuardian</h1>
            </div>
          </div>

          <h2 className="auth-hero-title">
            Diagnóstico automático de salud y rendimiento para tus bases PostgreSQL.
          </h2>
          <p className="auth-hero-desc">
            Carga tus scripts <code className="mono">.sql</code> para validarlos en un
            sandbox aislado u obtén el análisis integral de índices, bloat, consultas y
            parámetros del motor con un Health Score accionable en español.
          </p>

          <ul className="auth-highlights">
            <li>
              <strong>Análisis aislado por script:</strong> validación AST previa y ejecución
              segura en bases temporales sin tocar la aplicación.
            </li>
            <li>
              <strong>Diagnóstico en 5 pilares:</strong> índices, bloat, queries lentas,
              configuración y salud general con SQL de remediación listo para copiar.
            </li>
            <li>
              <strong>Acceso protegido:</strong> historial privado por usuario, hashing
              Argon2id OWASP y sesiones autenticadas.
            </li>
          </ul>
        </section>

        <section className="auth-panel" aria-label="Acceso a PgGuardian">
          <div className="auth-tabs" role="tablist" aria-label="Opciones de acceso">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'login'}
              className={`auth-tab ${activeTab === 'login' ? 'auth-tab--active' : ''}`}
              onClick={() => switchTab('login')}
              disabled={isSubmitting}
            >
              Iniciar sesión
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'register'}
              className={`auth-tab ${activeTab === 'register' ? 'auth-tab--active' : ''}`}
              onClick={() => switchTab('register')}
              disabled={isSubmitting}
            >
              Crear cuenta
            </button>
          </div>

          {error && (
            <div className="auth-alert auth-alert--error" role="alert">
              {error}
            </div>
          )}

          {activeTab === 'login' ? (
            <form className="auth-form" onSubmit={handleLoginSubmit} noValidate>
              <div className="auth-field">
                <label htmlFor="login-email" className="auth-label">
                  Correo electrónico
                </label>
                <input
                  id="login-email"
                  name="email"
                  type="email"
                  className="auth-input"
                  placeholder="tu@empresa.com"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  autoComplete="email"
                  disabled={isSubmitting}
                  required
                />
              </div>

              <div className="auth-field">
                <div className="auth-label-row">
                  <label htmlFor="login-password" className="auth-label">
                    Contraseña
                  </label>
                  <button
                    type="button"
                    className="auth-toggle-btn"
                    onClick={() => setShowPasswords((v) => !v)}
                    disabled={isSubmitting}
                  >
                    {showPasswords ? 'Ocultar' : 'Mostrar'}
                  </button>
                </div>
                <input
                  id="login-password"
                  name="password"
                  type={showPasswords ? 'text' : 'password'}
                  className="auth-input"
                  placeholder="Ingresa tu contraseña"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  autoComplete="current-password"
                  disabled={isSubmitting}
                  required
                />
              </div>

              <button type="submit" className="auth-submit-btn" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <span className="spinner" aria-hidden="true"></span>
                    Ingresando…
                  </>
                ) : (
                  'Iniciar sesión'
                )}
              </button>
            </form>
          ) : (
            <form className="auth-form" onSubmit={handleRegisterSubmit} noValidate>
              <div className="auth-field">
                <label htmlFor="reg-name" className="auth-label">
                  Nombre completo
                </label>
                <input
                  id="reg-name"
                  name="name"
                  type="text"
                  className="auth-input"
                  placeholder="Ej. Ana López"
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  autoComplete="name"
                  maxLength={150}
                  disabled={isSubmitting}
                  required
                />
                {regAttempted && !regNameOk && (
                  <span className="auth-field-error">El nombre es obligatorio.</span>
                )}
              </div>

              <div className="auth-field">
                <label htmlFor="reg-email" className="auth-label">
                  Correo electrónico
                </label>
                <input
                  id="reg-email"
                  name="email"
                  type="email"
                  className="auth-input"
                  placeholder="ana@empresa.com"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  autoComplete="email"
                  maxLength={255}
                  disabled={isSubmitting}
                  required
                />
                {(regEmail.length > 0 || regAttempted) && !regEmailOk && (
                  <span className="auth-field-error">Ingresa un correo electrónico válido.</span>
                )}
              </div>

              <div className="auth-field">
                <div className="auth-label-row">
                  <label htmlFor="reg-password" className="auth-label">
                    Contraseña
                  </label>
                  <button
                    type="button"
                    className="auth-toggle-btn"
                    onClick={() => setShowPasswords((v) => !v)}
                    disabled={isSubmitting}
                  >
                    {showPasswords ? 'Ocultar' : 'Mostrar'}
                  </button>
                </div>
                <input
                  id="reg-password"
                  name="password"
                  type={showPasswords ? 'text' : 'password'}
                  className="auth-input"
                  placeholder="Mínimo 12 caracteres únicos"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  autoComplete="new-password"
                  maxLength={128}
                  disabled={isSubmitting}
                  required
                />
              </div>

              <div className="auth-field">
                <label htmlFor="reg-password-confirm" className="auth-label">
                  Confirmar contraseña
                </label>
                <input
                  id="reg-password-confirm"
                  name="password_confirm"
                  type={showPasswords ? 'text' : 'password'}
                  className="auth-input"
                  placeholder="Repite tu contraseña"
                  value={regPasswordConfirm}
                  onChange={(e) => setRegPasswordConfirm(e.target.value)}
                  autoComplete="new-password"
                  maxLength={128}
                  disabled={isSubmitting}
                  required
                />
              </div>

              <div className="auth-checklist" aria-live="polite">
                <div className="auth-checklist-title">Requisitos de contraseña</div>
                <ul className="auth-checklist-items">
                  {regRules.map((rule) => (
                    <li key={rule.id} className={`auth-check auth-check--${rule.state}`}>
                      <span aria-hidden="true">
                        {rule.state === 'ok' ? '✓' : rule.state === 'error' ? '✕' : '•'}
                      </span>
                      <span>{rule.label}</span>
                    </li>
                  ))}
                  <li className="auth-check auth-check--info">
                    <span aria-hidden="true">ℹ</span>
                    <span>El servidor también rechaza contraseñas comunes conocidas.</span>
                  </li>
                </ul>
              </div>

              <button type="submit" className="auth-submit-btn" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <span className="spinner" aria-hidden="true"></span>
                    Creando cuenta…
                  </>
                ) : (
                  'Crear cuenta y entrar'
                )}
              </button>
            </form>
          )}
        </section>
      </div>
    </div>
  )
}


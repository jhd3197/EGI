import { useEgi } from './store.js'
import { buildView } from './lib/view.js'
import { useI18n } from './i18n/index.js'
import AuthScreen from './components/AuthScreen.jsx'
import DisasterPicker from './components/DisasterPicker.jsx'
import AppShell from './components/AppShell.jsx'

export default function App() {
  const { state, actions } = useEgi()
  const { t } = useI18n()
  const view = buildView(state, actions, t)

  if (view.showAuth) return <AuthScreen view={view} actions={actions} />
  if (view.showPicker) return <DisasterPicker view={view} actions={actions} />
  return <AppShell view={view} actions={actions} />
}

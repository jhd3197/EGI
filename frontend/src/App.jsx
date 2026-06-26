import { useEgi } from './store.js'
import { buildView } from './lib/view.js'
import AuthScreen from './components/AuthScreen.jsx'
import DisasterPicker from './components/DisasterPicker.jsx'
import AppShell from './components/AppShell.jsx'

export default function App() {
  const { state, actions } = useEgi()
  const view = buildView(state, actions)

  if (view.showAuth) return <AuthScreen view={view} actions={actions} />
  if (view.showPicker) return <DisasterPicker view={view} actions={actions} />
  return <AppShell view={view} actions={actions} />
}

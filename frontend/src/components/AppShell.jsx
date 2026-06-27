import { css } from '../lib/css.js'
import Sidebar from './Sidebar.jsx'
import TopBar from './TopBar.jsx'
import ConnectionBanner from './ConnectionBanner.jsx'
import TabBar from './TabBar.jsx'
import ReportSheet from './ReportSheet.jsx'
import HomeScreen from './HomeScreen.jsx'
import SearchScreen from './SearchScreen.jsx'
import PersonDetail from './PersonDetail.jsx'
import SheltersScreen from './SheltersScreen.jsx'
import MyReportsScreen from './MyReportsScreen.jsx'
import MeshScreen from './MeshScreen.jsx'
import MapScreen from './MapScreen.jsx'
import MeshWarningModal from './MeshWarningModal.jsx'
import DuplicatesScreen from './DuplicatesScreen.jsx'
import ModerationScreen from './ModerationScreen.jsx'
import DashboardScreen from './DashboardScreen.jsx'

export default function AppShell({ view, actions }) {
  const v = view
  return (
    <div style={{ ...css("height:100vh;width:100%;display:flex;background:#F4EFE7;font-family:'IBM Plex Sans',system-ui,sans-serif;overflow:hidden;"), flexDirection: v.rootDir }}>
      <Sidebar view={v} actions={actions} />

      <div style={css('flex:1;display:flex;flex-direction:column;min-width:0;height:100%;')}>
        <TopBar view={v} actions={actions} />
        <ConnectionBanner view={v} />

        <div style={css('flex:1;position:relative;display:flex;flex-direction:column;min-height:0;')}>
          <div className="egi-scroll" style={css('flex:1;overflow-y:auto;overflow-x:hidden;')}>
            <div style={{ ...css('margin:0 auto;width:100%;'), maxWidth: v.contentMaxW }}>
              {v.isHome && <HomeScreen view={v} actions={actions} />}
              {v.isSearch && <SearchScreen view={v} actions={actions} />}
              {v.isDetail && <PersonDetail view={v} actions={actions} />}
              {v.isShelters && <SheltersScreen view={v} actions={actions} />}
              {v.isMine && <MyReportsScreen view={v} actions={actions} />}
              {v.isMesh && <MeshScreen view={v} actions={actions} />}
              {v.isMap && <MapScreen view={v} actions={actions} />}
              {v.isDuplicates && <DuplicatesScreen view={v} actions={actions} />}
              {v.isModeration && <ModerationScreen view={v} actions={actions} />}
              {v.isDashboard && <DashboardScreen view={v} actions={actions} />}
            </div>
          </div>

          <TabBar view={v} actions={actions} />

          {v.reportOpen && <ReportSheet view={v} actions={actions} />}
          <MeshWarningModal view={v} actions={actions} />
        </div>
      </div>
    </div>
  )
}

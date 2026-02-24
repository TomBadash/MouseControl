import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import "Theme.js" as Theme

/*  Per-application profile management page.
    Left panel: profile list.  Right panel: profile detail & mappings.  */

Item {
    id: profilesPage

    // ── State ─────────────────────────────────────────────────
    property string selectedProfile: ""
    property string selectedProfileLabel: ""
    property var    selectedProfileApps: []
    property var    profileMappings: []

    function selectProfile(name) {
        selectedProfile = name
        var profs = backend.profiles
        for (var i = 0; i < profs.length; i++) {
            if (profs[i].name === name) {
                selectedProfileLabel = profs[i].label
                selectedProfileApps  = profs[i].apps
                break
            }
        }
        profileMappings = backend.getProfileMappings(name)
    }

    Connections {
        target: backend
        function onProfilesChanged() {
            if (selectedProfile !== "")
                profileMappings = backend.getProfileMappings(selectedProfile)
        }
    }

    // ── Layout ────────────────────────────────────────────────
    Column {
        anchors.fill: parent
        spacing: 0

        // Header
        Item {
            width: parent.width; height: 90

            Column {
                anchors {
                    left: parent.left; leftMargin: 36
                    verticalCenter: parent.verticalCenter
                }
                spacing: 4

                Text {
                    text: "Application Profiles"
                    font { family: Theme.fontFamily; pixelSize: 24; bold: true }
                    color: Theme.textPrimary
                }
                Text {
                    text: "Automatically switch button mappings per application"
                    font { family: Theme.fontFamily; pixelSize: 13 }
                    color: Theme.textSecondary
                }
            }
        }

        Rectangle {
            width: parent.width - 72; height: 1
            color: Theme.border
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Item { width: 1; height: 24 }

        // Two-column layout
        Row {
            anchors {
                left: parent.left; leftMargin: 36
                right: parent.right; rightMargin: 36
            }
            height: parent.height - 130
            spacing: 16

            // ── Left panel: profile list ──────────────────
            Rectangle {
                id: leftPanel
                width: 240
                height: parent.height
                radius: Theme.radius
                color: Theme.bgCard
                border.width: 1; border.color: Theme.border
                clip: true

                Column {
                    anchors.fill: parent
                    spacing: 0

                    // Title
                    Item {
                        width: parent.width; height: 48

                        Text {
                            anchors {
                                left: parent.left; leftMargin: 16
                                verticalCenter: parent.verticalCenter
                            }
                            text: "Profiles"
                            font { family: Theme.fontFamily; pixelSize: 14; bold: true }
                            color: Theme.textPrimary
                        }
                    }

                    Rectangle {
                        width: parent.width; height: 1
                        color: Theme.border
                    }

                    // Profile items
                    ListView {
                        id: profileList
                        width: parent.width
                        height: parent.height - 110
                        model: backend.profiles
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds

                        delegate: Rectangle {
                            width: profileList.width
                            height: 60
                            color: selectedProfile === modelData.name
                                   ? Qt.rgba(0, 0.83, 0.67, 0.08)
                                   : profItemMa.containsMouse
                                     ? Qt.rgba(1, 1, 1, 0.03)
                                     : "transparent"
                            Behavior on color { ColorAnimation { duration: 120 } }

                            Row {
                                anchors {
                                    fill: parent
                                    leftMargin: 8; rightMargin: 12
                                }
                                spacing: 10

                                // Active indicator
                                Rectangle {
                                    width: 4; height: 32; radius: 2
                                    color: modelData.isActive
                                           ? Theme.accent : "transparent"
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                // App icons row
                                Row {
                                    spacing: -6
                                    anchors.verticalCenter: parent.verticalCenter
                                    visible: modelData.appIcons !== undefined
                                             && modelData.appIcons.length > 0

                                    Repeater {
                                        model: modelData.appIcons
                                        delegate: Image {
                                            source: modelData
                                                    ? "file:///" + applicationDirPath
                                                      + "/images/" + modelData
                                                    : ""
                                            width: 30; height: 30
                                            sourceSize { width: 30; height: 30 }
                                            fillMode: Image.PreserveAspectFit
                                            visible: modelData !== ""
                                            smooth: true; mipmap: true
                                        }
                                    }
                                }

                                Column {
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 2

                                    Text {
                                        text: modelData.label
                                        font {
                                            family: Theme.fontFamily
                                            pixelSize: 13; bold: true
                                        }
                                        color: Theme.textPrimary
                                        elide: Text.ElideRight
                                        width: leftPanel.width - 80
                                    }
                                    Text {
                                        text: modelData.apps.length
                                              ? modelData.apps.join(", ")
                                              : "All applications"
                                        font { family: Theme.fontFamily; pixelSize: 10 }
                                        color: Theme.textSecondary
                                        elide: Text.ElideRight
                                        width: leftPanel.width - 80
                                    }
                                }
                            }

                            MouseArea {
                                id: profItemMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: selectProfile(modelData.name)
                            }
                        }
                    }

                    Rectangle {
                        width: parent.width; height: 1
                        color: Theme.border
                    }

                    // Add profile controls
                    Item {
                        width: parent.width; height: 56

                        RowLayout {
                            anchors {
                                fill: parent
                                leftMargin: 10; rightMargin: 10
                            }
                            spacing: 6

                            ComboBox {
                                id: addCombo
                                Layout.fillWidth: true
                                model: {
                                    var apps = backend.knownApps
                                    var labels = []
                                    for (var i = 0; i < apps.length; i++)
                                        labels.push(apps[i].label)
                                    return labels
                                }
                                Material.accent: Theme.accent
                                font { family: Theme.fontFamily; pixelSize: 11 }
                            }

                            Rectangle {
                                width: 48; height: 32; radius: 8
                                color: addBtnMa.containsMouse
                                       ? Theme.accentHover : Theme.accent

                                Text {
                                    anchors.centerIn: parent
                                    text: "+ Add"
                                    font {
                                        family: Theme.fontFamily
                                        pixelSize: 11; bold: true
                                    }
                                    color: Theme.bgSidebar
                                }

                                MouseArea {
                                    id: addBtnMa
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (addCombo.currentText)
                                            backend.addProfile(addCombo.currentText)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ── Right panel: profile detail ───────────────
            Rectangle {
                width: parent.width - leftPanel.width - 16
                height: parent.height
                radius: Theme.radius
                color: Theme.bgCard
                border.width: 1; border.color: Theme.border
                clip: true

                Column {
                    anchors {
                        fill: parent; margins: 20
                    }
                    spacing: 12
                    visible: selectedProfile !== ""

                    // Profile title
                    Text {
                        text: selectedProfileLabel
                        font { family: Theme.fontFamily; pixelSize: 18; bold: true }
                        color: Theme.textPrimary
                    }
                    // App list with icons
                    Row {
                        spacing: 8

                        Repeater {
                            model: selectedProfileApps
                            delegate: Row {
                                spacing: 5

                                Image {
                                    property string iconFile: {
                                        var apps = backend.knownApps
                                        for (var i = 0; i < apps.length; i++) {
                                            if (apps[i].exe === modelData)
                                                return apps[i].icon
                                        }
                                        return ""
                                    }
                                    source: iconFile
                                            ? "file:///" + applicationDirPath
                                              + "/images/" + iconFile
                                            : ""
                                    width: 32; height: 32
                                    sourceSize { width: 32; height: 32 }
                                    fillMode: Image.PreserveAspectFit
                                    visible: iconFile !== ""
                                    smooth: true; mipmap: true
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: modelData
                                    font { family: Theme.fontFamily; pixelSize: 12 }
                                    color: Theme.textSecondary
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }

                        Text {
                            text: "Applies to all apps not assigned to a specific profile"
                            font { family: Theme.fontFamily; pixelSize: 12 }
                            color: Theme.textSecondary
                            visible: selectedProfileApps.length === 0
                        }
                    }

                    Item { width: 1; height: 8 }

                    // Per-button mapping rows
                    Repeater {
                        model: profileMappings

                        delegate: Rectangle {
                            width: parent.width
                            height: 48; radius: 8
                            color: Theme.bgSidebar

                            RowLayout {
                                anchors {
                                    fill: parent
                                    leftMargin: 16; rightMargin: 16
                                }
                                spacing: 12

                                Text {
                                    text: modelData.name
                                    font { family: Theme.fontFamily; pixelSize: 13 }
                                    color: Theme.textPrimary
                                    Layout.preferredWidth: 180
                                }

                                ComboBox {
                                    id: mappingCombo
                                    Layout.fillWidth: true
                                    model: backend.allActions
                                    textRole: "label"
                                    valueRole: "id"
                                    Material.accent: Theme.accent
                                    font { family: Theme.fontFamily; pixelSize: 12 }

                                    // Find the index matching current action
                                    Component.onCompleted: setIndex()

                                    function setIndex() {
                                        var acts = backend.allActions
                                        for (var j = 0; j < acts.length; j++) {
                                            if (acts[j].id === modelData.actionId) {
                                                currentIndex = j
                                                return
                                            }
                                        }
                                        currentIndex = 0
                                    }

                                    onActivated: {
                                        backend.setProfileMapping(
                                            selectedProfile, modelData.key,
                                            currentValue)
                                    }
                                }
                            }
                        }
                    }

                    Item { width: 1; height: 8 }

                    // Delete button (not for default)
                    Rectangle {
                        visible: selectedProfile !== "" && selectedProfile !== "default"
                        width: delText.implicitWidth + 28
                        height: 36; radius: 8
                        color: delMa.containsMouse ? "#aa3333" : "#662222"
                        Behavior on color { ColorAnimation { duration: 120 } }

                        Text {
                            id: delText
                            anchors.centerIn: parent
                            text: "Delete Profile"
                            font { family: Theme.fontFamily; pixelSize: 12; bold: true }
                            color: Theme.textPrimary
                        }

                        MouseArea {
                            id: delMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                backend.deleteProfile(selectedProfile)
                                selectedProfile = ""
                                selectedProfileLabel = ""
                                selectedProfileApps = []
                                profileMappings = []
                            }
                        }
                    }

                    // Active badge
                    Row {
                        spacing: 6
                        visible: isSelectedProfileActive()

                        function isSelectedProfileActive() {
                            if (selectedProfile === "") return false
                            var profs = backend.profiles
                            for (var i = 0; i < profs.length; i++) {
                                if (profs[i].name === selectedProfile)
                                    return profs[i].isActive
                            }
                            return false
                        }

                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: Theme.accent
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: "Currently active"
                            font { family: Theme.fontFamily; pixelSize: 12 }
                            color: Theme.accent
                        }
                    }
                }

                // Empty state
                Column {
                    anchors.centerIn: parent
                    spacing: 8
                    visible: selectedProfile === ""

                    Text {
                        text: "Select a profile"
                        anchors.horizontalCenter: parent.horizontalCenter
                        font { family: Theme.fontFamily; pixelSize: 16; bold: true }
                        color: Theme.textDim
                    }
                    Text {
                        text: "Click a profile on the left to view its settings"
                        anchors.horizontalCenter: parent.horizontalCenter
                        font { family: Theme.fontFamily; pixelSize: 12 }
                        color: Theme.textDim
                    }
                }
            }
        }
    }
}

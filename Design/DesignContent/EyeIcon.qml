import QtQuick

Item {
    id: root
    width: 16
    height: 14

    property bool isVisible: false
    property color eyeColor: "#666666"

    Canvas {
        id: eyeCanvas
        anchors.centerIn: parent
        width: 16
        height: 14
        property bool isVisible: root.isVisible
        property color eyeColor: root.eyeColor

        onIsVisibleChanged: requestPaint()
        onEyeColorChanged: requestPaint()

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            ctx.strokeStyle = eyeColor;
            ctx.lineWidth = 1.3;
            ctx.lineCap = "round";
            ctx.lineJoin = "round";

            var w = width;
            var h = height;

            // Contorno do olho
            ctx.beginPath();
            ctx.moveTo(1, h / 2);
            ctx.quadraticCurveTo(w / 2, 0.5, w - 1, h / 2);
            ctx.quadraticCurveTo(w / 2, h - 0.5, 1, h / 2);
            ctx.stroke();

            // Pupila
            ctx.beginPath();
            ctx.arc(w / 2, h / 2, 2.2, 0, 2 * Math.PI);
            if (isVisible) {
                ctx.fillStyle = eyeColor;
                ctx.fill();
            } else {
                ctx.stroke();
                // Linha diagonal cortando o olho quando oculto
                ctx.beginPath();
                ctx.moveTo(2, 2);
                ctx.lineTo(w - 2, h - 2);
                ctx.stroke();
            }
        }
    }
}

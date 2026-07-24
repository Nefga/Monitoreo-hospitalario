/*
 * ClienteMonitoreoHospitalario.java
 * ----------------------------------
 * Cliente de escritorio en Java (Swing) para el sistema de Monitoreo
 * Ambiental Hospitalario — versión MULTI-CUARTO.
 *
 * Se conecta por TCP al servidor_central.py (127.0.0.1:5050), recibe una
 * lectura JSON por línea (cada una con cuarto_id y cuarto_nombre) y va
 * creando/actualizando una tarjeta por cada cuarto que aparece, igual
 * que el dashboard web.
 *
 * No requiere librerías externas: incluye un parser JSON minimalista
 * propio (analizarJsonPlano) suficiente para el formato plano que envía
 * el servidor, por lo que basta con compilar este único archivo.
 *
 * Compilar y ejecutar:
 *   javac ClienteMonitoreoHospitalario.java
 *   java ClienteMonitoreoHospitalario
 *
 * Instituto Tecnologico de Tijuana
 * Por: Nicole Lewis, Farid Garcia
 */

import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.border.LineBorder;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.Socket;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.TreeSet;

public class ClienteMonitoreoHospitalario extends JFrame {

    private static final String HOST = "127.0.0.1";
    private static final int PUERTO = 5050;   // 5000 choca con AirPlay Receiver en macOS

    private static final double TEMP_MAX = 28.0;
    private static final double HUMEDAD_MAX = 70.0;
    private static final double CO2_MAX = 1000.0;

    private static final Color AZUL_OSCURO = new Color(0x0D, 0x1B, 0x3E);
    private static final Color AZUL_MEDIO = new Color(0x16, 0x28, 0x5C);
    private static final Color AMARILLO = new Color(0xF2, 0xB7, 0x05);
    private static final Color ROJO_ALERTA = new Color(0xE2, 0x3B, 0x3B);
    private static final Color TEXTO_CLARO = new Color(0xF4, 0xF6, 0xFB);
    private static final Color TEXTO_TENUE = new Color(0xB9, 0xC2, 0xDD);

    // Misma paleta que la gráfica de matplotlib y el dashboard web
    private static final Color[] PALETA = {
            new Color(0x4C, 0x8D, 0xFF), new Color(0xFF, 0x9F, 0x40),
            new Color(0x4C, 0xAF, 0x50), new Color(0xE2, 0x3B, 0x3B),
            new Color(0xB9, 0x83, 0xFF), new Color(0xFF, 0xD4, 0x5C),
            new Color(0x39, 0xC0, 0xC8), new Color(0xFF, 0x6F, 0xA5),
    };

    private static Color colorDeCuarto(int cuartoId) {
        return PALETA[(cuartoId - 1) % PALETA.length];
    }

    private JLabel bannerAlerta;
    private JLabel estadoConexion;
    private JPanel cuartosPanel;
    private DefaultTableModel modeloTabla;

    private final Map<Integer, TarjetaCuarto> tarjetasPorCuarto = new LinkedHashMap<>();
    private final TreeSet<Integer> cuartosEnAlerta = new TreeSet<>();

    public ClienteMonitoreoHospitalario() {
        super("Monitoreo Ambiental Hospitalario - Cliente Java");
        construirInterfaz();
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setSize(820, 700);
        setLocationRelativeTo(null);
        setVisible(true);

        Thread hiloConexion = new Thread(this::bucleConexion);
        hiloConexion.setDaemon(true);
        hiloConexion.start();
    }

    private void construirInterfaz() {
        getContentPane().setBackground(AZUL_OSCURO);
        setLayout(new BorderLayout(10, 10));

        // ---------- Encabezado ----------
        JPanel encabezado = new JPanel();
        encabezado.setLayout(new BoxLayout(encabezado, BoxLayout.Y_AXIS));
        encabezado.setBackground(AZUL_OSCURO);
        encabezado.setBorder(new EmptyBorder(16, 16, 8, 16));

        JLabel titulo = new JLabel("Monitoreo Ambiental Hospitalario");
        titulo.setFont(new Font("SansSerif", Font.BOLD, 22));
        titulo.setForeground(TEXTO_CLARO);
        titulo.setAlignmentX(Component.CENTER_ALIGNMENT);

        JLabel subtitulo = new JLabel("Todos los cuartos — luz, temperatura, humedad, calidad del aire");
        subtitulo.setFont(new Font("SansSerif", Font.ITALIC, 13));
        subtitulo.setForeground(TEXTO_TENUE);
        subtitulo.setAlignmentX(Component.CENTER_ALIGNMENT);

        estadoConexion = new JLabel("● Conectando al servidor...");
        estadoConexion.setForeground(AMARILLO);
        estadoConexion.setAlignmentX(Component.CENTER_ALIGNMENT);

        encabezado.add(titulo);
        encabezado.add(subtitulo);
        encabezado.add(Box.createVerticalStrut(6));
        encabezado.add(estadoConexion);

        bannerAlerta = new JLabel("", SwingConstants.CENTER);
        bannerAlerta.setOpaque(true);
        bannerAlerta.setBackground(ROJO_ALERTA);
        bannerAlerta.setForeground(Color.WHITE);
        bannerAlerta.setFont(new Font("SansSerif", Font.BOLD, 14));
        bannerAlerta.setBorder(new EmptyBorder(8, 8, 8, 8));
        bannerAlerta.setVisible(false);

        JPanel panelSuperior = new JPanel(new BorderLayout());
        panelSuperior.setBackground(AZUL_OSCURO);
        panelSuperior.add(encabezado, BorderLayout.NORTH);
        panelSuperior.add(bannerAlerta, BorderLayout.SOUTH);
        add(panelSuperior, BorderLayout.NORTH);

        // ---------- Panel central: tarjetas de cuartos (arriba) + historial (abajo) ----------
        JPanel centro = new JPanel();
        centro.setLayout(new BoxLayout(centro, BoxLayout.Y_AXIS));
        centro.setBackground(AZUL_OSCURO);

        // Cuadrícula de tarjetas, se va llenando sola conforme llegan cuartos
        cuartosPanel = new JPanel(new FlowLayout(FlowLayout.LEFT, 12, 12));
        cuartosPanel.setBackground(AZUL_OSCURO);
        JScrollPane scrollCuartos = new JScrollPane(cuartosPanel);
        scrollCuartos.setBorder(new EmptyBorder(0, 10, 0, 10));
        scrollCuartos.getViewport().setBackground(AZUL_OSCURO);
        scrollCuartos.setPreferredSize(new Dimension(780, 260));

        // ---------- Tabla de historial (todos los cuartos) ----------
        String[] columnas = {"Cuarto", "Hora", "Luz", "Temp (°C)", "Humedad (%)", "CO2 (ppm)", "Estado"};
        modeloTabla = new DefaultTableModel(columnas, 0) {
            @Override
            public boolean isCellEditable(int row, int col) { return false; }
        };
        JTable tabla = new JTable(modeloTabla);
        tabla.setBackground(AZUL_MEDIO);
        tabla.setForeground(TEXTO_CLARO);
        tabla.setGridColor(AZUL_OSCURO);
        tabla.getTableHeader().setBackground(AZUL_OSCURO);
        tabla.getTableHeader().setForeground(AMARILLO);
        tabla.setRowHeight(24);

        JScrollPane scrollTabla = new JScrollPane(tabla);
        scrollTabla.setBorder(new EmptyBorder(10, 10, 10, 10));
        scrollTabla.getViewport().setBackground(AZUL_MEDIO);

        centro.add(scrollCuartos);
        centro.add(scrollTabla);
        add(centro, BorderLayout.CENTER);
    }

    /** Tarjeta visual de un cuarto: se crea una vez y se va actualizando en el mismo lugar. */
    private class TarjetaCuarto extends JPanel {
        private final JLabel labelEstado;
        private final JLabel valorLux, valorTemp, valorHumedad, valorCo2;

        TarjetaCuarto(int cuartoId, String nombre) {
            setLayout(new BoxLayout(this, BoxLayout.Y_AXIS));
            setBackground(AZUL_MEDIO);
            setPreferredSize(new Dimension(170, 210));
            setBorder(BorderFactory.createCompoundBorder(
                    new LineBorder(colorDeCuarto(cuartoId), 3, true),
                    new EmptyBorder(10, 12, 10, 12)));

            JPanel fila = new JPanel(new BorderLayout());
            fila.setBackground(AZUL_MEDIO);
            JLabel nombreLbl = new JLabel(nombre != null ? nombre : ("Cuarto " + cuartoId));
            nombreLbl.setForeground(TEXTO_CLARO);
            nombreLbl.setFont(new Font("SansSerif", Font.BOLD, 14));
            labelEstado = new JLabel("🟢");
            fila.add(nombreLbl, BorderLayout.WEST);
            fila.add(labelEstado, BorderLayout.EAST);
            fila.setAlignmentX(Component.LEFT_ALIGNMENT);

            valorLux = crearFilaDato("💡 Luz");
            valorTemp = crearFilaDato("🌡 Temp");
            valorHumedad = crearFilaDato("💧 Hum");
            valorCo2 = crearFilaDato("🫧 Aire");

            add(fila);
            add(Box.createVerticalStrut(8));
            add(filaCompleta("💡 Luz", valorLux));
            add(filaCompleta("🌡 Temp", valorTemp));
            add(filaCompleta("💧 Hum", valorHumedad));
            add(filaCompleta("🫧 Aire", valorCo2));
        }

        private JLabel crearFilaDato(String etiqueta) {
            JLabel valor = new JLabel("--");
            valor.setForeground(AMARILLO);
            valor.setFont(new Font("SansSerif", Font.BOLD, 13));
            return valor;
        }

        private JPanel filaCompleta(String etiquetaTexto, JLabel valorLabel) {
            JPanel p = new JPanel(new BorderLayout());
            p.setBackground(AZUL_MEDIO);
            p.setAlignmentX(Component.LEFT_ALIGNMENT);
            JLabel etiqueta = new JLabel(etiquetaTexto);
            etiqueta.setForeground(TEXTO_TENUE);
            etiqueta.setFont(new Font("SansSerif", Font.PLAIN, 12));
            p.add(etiqueta, BorderLayout.WEST);
            p.add(valorLabel, BorderLayout.EAST);
            return p;
        }

        void actualizar(double lux, double temp, double humedad, double co2, boolean critico) {
            valorLux.setText(formatear(lux));
            valorTemp.setText(formatear(temp));
            valorHumedad.setText(formatear(humedad));
            valorCo2.setText(formatear(co2));
            labelEstado.setText(critico ? "🔴" : "🟢");
        }
    }

    /** Se reconecta automáticamente si el servidor central no está disponible. */
    private void bucleConexion() {
        while (true) {
            try (Socket socket = new Socket(HOST, PUERTO);
                 BufferedReader in = new BufferedReader(
                         new InputStreamReader(socket.getInputStream()))) {

                actualizarEstadoConexion(true);

                String linea;
                while ((linea = in.readLine()) != null) {
                    if (linea.trim().isEmpty()) continue;
                    Map<String, String> datos = analizarJsonPlano(linea);
                    if (datos != null) {
                        SwingUtilities.invokeLater(() -> procesarLectura(datos));
                    }
                }
            } catch (IOException e) {
                actualizarEstadoConexion(false);
            }

            try {
                Thread.sleep(3000); // reintentar conexión cada 3s
            } catch (InterruptedException ignored) {
            }
        }
    }

    private void actualizarEstadoConexion(boolean ok) {
        SwingUtilities.invokeLater(() -> {
            if (ok) {
                estadoConexion.setText("● Conectado al servidor central");
                estadoConexion.setForeground(new Color(0x4C, 0xAF, 0x50));
            } else {
                estadoConexion.setText("● Sin conexión — reintentando...");
                estadoConexion.setForeground(ROJO_ALERTA);
            }
        });
    }

    private void procesarLectura(Map<String, String> datos) {
        Integer cuartoId = parseIntSeguro(datos.get("cuarto_id"));
        if (cuartoId == null) return;
        String cuartoNombre = datos.get("cuarto_nombre");

        double lux = parseDoubleSeguro(datos.get("lux"));
        double temp = parseDoubleSeguro(datos.get("temp"));
        double humedad = parseDoubleSeguro(datos.get("humedad"));
        double co2 = parseDoubleSeguro(datos.get("co2_ppm"));
        boolean buzzer = "true".equalsIgnoreCase(datos.get("buzzer"));

        TarjetaCuarto tarjeta = tarjetasPorCuarto.get(cuartoId);
        if (tarjeta == null) {
            tarjeta = new TarjetaCuarto(cuartoId, cuartoNombre);
            tarjetasPorCuarto.put(cuartoId, tarjeta);
            cuartosPanel.add(tarjeta);
            cuartosPanel.revalidate();
            cuartosPanel.repaint();
        }
        tarjeta.actualizar(lux, temp, humedad, co2, buzzer);

        if (buzzer) {
            cuartosEnAlerta.add(cuartoId);
            Toolkit.getDefaultToolkit().beep();
        } else {
            cuartosEnAlerta.remove(cuartoId);
        }
        actualizarBannerGlobal();

        String hora = LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm:ss"));
        modeloTabla.insertRow(0, new Object[]{
                cuartoId, hora, formatear(lux), formatear(temp), formatear(humedad),
                formatear(co2), buzzer ? "🔴 Alerta" : "🟢 Normal"
        });
        while (modeloTabla.getRowCount() > 30) {
            modeloTabla.removeRow(modeloTabla.getRowCount() - 1);
        }
    }

    private void actualizarBannerGlobal() {
        if (cuartosEnAlerta.isEmpty()) {
            bannerAlerta.setVisible(false);
            return;
        }
        StringBuilder sb = new StringBuilder("⚠ ALERTA en cuarto(s): ");
        boolean primero = true;
        for (int id : cuartosEnAlerta) {
            if (!primero) sb.append(", ");
            sb.append(id);
            primero = false;
        }
        bannerAlerta.setText(sb.toString());
        bannerAlerta.setVisible(true);
    }

    private String formatear(double valor) {
        return String.format("%.1f", valor);
    }

    private double parseDoubleSeguro(String texto) {
        try {
            return texto == null ? 0.0 : Double.parseDouble(texto);
        } catch (NumberFormatException e) {
            return 0.0;
        }
    }

    private Integer parseIntSeguro(String texto) {
        try {
            return texto == null ? null : (int) Double.parseDouble(texto);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /**
     * Parser JSON minimalista para objetos planos de un solo nivel, del tipo:
     * {"cuarto_id":1,"cuarto_nombre":"Cuarto 1","lux":123.4,"temp":25.6,...}
     * No soporta objetos anidados ni arreglos (no se necesitan aquí).
     */
    private Map<String, String> analizarJsonPlano(String json) {
        Map<String, String> resultado = new HashMap<>();
        String contenido = json.trim();
        if (contenido.startsWith("{")) contenido = contenido.substring(1);
        if (contenido.endsWith("}")) contenido = contenido.substring(0, contenido.length() - 1);

        int nivel = 0;
        StringBuilder actual = new StringBuilder();
        java.util.List<String> pares = new java.util.ArrayList<>();
        boolean dentroDeString = false;

        for (char c : contenido.toCharArray()) {
            if (c == '"') dentroDeString = !dentroDeString;
            if (!dentroDeString) {
                if (c == '{' || c == '[') nivel++;
                if (c == '}' || c == ']') nivel--;
            }
            if (c == ',' && nivel == 0 && !dentroDeString) {
                pares.add(actual.toString());
                actual.setLength(0);
            } else {
                actual.append(c);
            }
        }
        if (actual.length() > 0) pares.add(actual.toString());

        for (String par : pares) {
            int idx = buscarPrimerosDosPuntosFueraDeString(par);
            if (idx == -1) continue;
            String clave = par.substring(0, idx).trim().replaceAll("^\"|\"$", "");
            String valor = par.substring(idx + 1).trim().replaceAll("^\"|\"$", "");
            resultado.put(clave, valor);
        }
        return resultado.isEmpty() ? null : resultado;
    }

    /** Busca el ':' que separa clave de valor, ignorando los ':' que pudieran
     * aparecer dentro de un valor de texto entre comillas. */
    private int buscarPrimerosDosPuntosFueraDeString(String par) {
        boolean dentroDeString = false;
        for (int i = 0; i < par.length(); i++) {
            char c = par.charAt(i);
            if (c == '"') dentroDeString = !dentroDeString;
            if (c == ':' && !dentroDeString) return i;
        }
        return -1;
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(ClienteMonitoreoHospitalario::new);
    }
}

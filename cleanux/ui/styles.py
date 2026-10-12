"""
Estilos CSS para o Cleanux.
Garante interface moderna, elegante e perfeitamente integrada ao tema do sistema (Adwaita/Zorin OS).
"""

CUSTOM_CSS = """
/* Barra de uso de disco e cartões de destaque */
.disk-card {
    background: alpha(@theme_selected_bg_color, 0.08);
    border: 1px solid alpha(@theme_selected_bg_color, 0.2);
    border-radius: 14px;
    padding: 18px 20px;
}

.disk-metric-title {
    font-size: 13px;
    font-weight: 500;
    opacity: 0.75;
}

.disk-metric-value {
    font-size: 22px;
    font-weight: 700;
}

.disk-percent-badge {
    font-size: 15px;
    font-weight: bold;
    padding: 4px 10px;
    border-radius: 9999px;
    background: alpha(@theme_selected_bg_color, 0.2);
    color: @theme_selected_bg_color;
}

/* Indicadores de status */
.badge-safe {
    font-size: 11px;
    font-weight: 600;
    background: alpha(#2ec27e, 0.2);
    color: #2ec27e;
    border-radius: 6px;
    padding: 2px 8px;
}

.badge-size {
    font-size: 13px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
    background: alpha(@theme_fg_color, 0.07);
}

.badge-rank {
    font-size: 13px;
    font-weight: 800;
    min-width: 30px;
    padding: 4px 8px;
    border-radius: 8px;
    background: alpha(@theme_selected_bg_color, 0.15);
    color: @theme_selected_bg_color;
}

.badge-rank-1 {
    background: #e5a50a;
    color: #ffffff;
    font-weight: 900;
}

.badge-rank-2 {
    background: #9a9996;
    color: #ffffff;
    font-weight: 900;
}

.badge-rank-3 {
    background: #b5835a;
    color: #ffffff;
    font-weight: 900;
}

.badge-source {
    font-size: 11px;
    font-weight: 500;
    opacity: 0.7;
    background: alpha(@theme_fg_color, 0.06);
    border-radius: 4px;
    padding: 2px 6px;
}

/* Barra de aplicativos mais pesados */
.app-row {
    padding: 10px 14px;
    border-radius: 10px;
    margin-bottom: 4px;
    background: alpha(@theme_fg_color, 0.03);
    border: 1px solid alpha(@theme_fg_color, 0.05);
}

.app-row:hover {
    background: alpha(@theme_fg_color, 0.06);
}

.app-name {
    font-size: 15px;
    font-weight: 600;
}

.app-size {
    font-size: 14px;
    font-weight: 700;
    color: @theme_selected_bg_color;
}

.clean-button-prominent {
    font-weight: 700;
    padding: 8px 18px;
    border-radius: 10px;
}

.card-title {
    font-size: 16px;
    font-weight: 700;
}
"""

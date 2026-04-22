###############################################################################
#### RANKING TOP 10 DEUDORES (por CUIT) + STACKED BAR POR ENTIDAD
####
#### Lógica correcta:
####   1. Agrupar por (situacion, nro_id/cuit, denominacion) → deuda_total_cuit
####   2. Rankear top 10 CUITs por deuda total dentro de cada situacion
####   3. Para cada CUIT del top 10, mostrar su deuda desagregada por entidad
####      → cada segmento de barra = una entidad financiera
###############################################################################

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json

# ── Asegurar tipos ──────────────────────────────────────────────────────────
df['prestamos']  = pd.to_numeric(df['prestamos'],  errors='coerce').fillna(0)
df['situacion']  = df['situacion'].astype(str)
df['nro_id']     = df['nro_id'].astype(str)
df['nombre_entidad'] = df['nombre_entidad'].fillna('Sin identificar')
df['denominacion']   = df['denominacion'].fillna(df['nro_id'])

sit_labels = {
    '1': 'Situación 1 · Cumplimiento Normal',
    '2': 'Situación 2 · Seguimiento Especial',
    '3': 'Situación 3 · Con Problemas',
    '4': 'Situación 4 · Alto Riesgo de Insolvencia',
    '5': 'Situación 5 · Irrecuperable',
}

# ── Paleta de colores por entidad ───────────────────────────────────────────
all_entities = sorted(df['nombre_entidad'].unique())
palette = (px.colors.qualitative.Bold +
           px.colors.qualitative.Vivid +
           px.colors.qualitative.Pastel)
entity_color = {ent: palette[i % len(palette)] for i, ent in enumerate(all_entities)}

# ── Construir datos por situación ───────────────────────────────────────────
tops    = {}   # top-10 CUITs por situacion (deuda total)
details = {}   # desglose por entidad para cada CUIT del top-10

for sit in ['1', '2', '3', '4', '5']:
    sub = df[df['situacion'] == sit].copy()

    # PASO 1: deuda total por CUIT (suma across todas las entidades)
    deuda_por_cuit = (
        sub.groupby(['nro_id', 'denominacion'])['prestamos']
        .sum()
        .reset_index()
        .rename(columns={'prestamos': 'deuda_total'})
        .sort_values('deuda_total', ascending=False)
        .head(10)
    )
    tops[sit] = deuda_por_cuit

    # PASO 2: para esos 10 CUITs, desglose por entidad
    top_cuits = deuda_por_cuit['nro_id'].tolist()
    desglose = (
        sub[sub['nro_id'].isin(top_cuits)]
        .groupby(['nro_id', 'denominacion', 'nombre_entidad'])['prestamos']
        .sum()
        .reset_index()
        .rename(columns={'prestamos': 'deuda_entidad'})
    )
    details[sit] = desglose

    print(f"\n{'─'*60}")
    print(f"  {sit_labels[sit]}")
    print(f"  Top 10 CUITs por deuda total:")
    print(deuda_por_cuit[['denominacion','deuda_total']]
          .rename(columns={'deuda_total':'Deuda ($)'})
          .to_string(index=False))

# ── Función para construir un gráfico por situación ─────────────────────────
def build_stacked_bar(sit):
    df_top   = tops[sit].sort_values('deuda_total', ascending=True)   # orden ascendente para barh
    df_det   = details[sit]

    # Etiquetas cortas para el eje Y
    df_top['label'] = df_top['denominacion'].str[:42]

    # Entidades que aparecen en este gráfico
    ents_in_sit = df_det['nombre_entidad'].unique()

    traces = []
    for ent in sorted(ents_in_sit):
        sub_ent = df_det[df_det['nombre_entidad'] == ent].set_index('nro_id')['deuda_entidad']

        x_vals = []
        for _, row in df_top.iterrows():
            x_vals.append(sub_ent.get(row['nro_id'], 0))

        # Etiqueta corta para leyenda
        ent_short = (ent.replace('BANCO ', '').replace(' S.A.U.', '')
                        .replace(' S.A.', '').replace(' SOCIEDAD ANONIMA','')[:28])

        traces.append(go.Bar(
            orientation='h',
            name=ent_short,
            y=df_top['label'].tolist(),
            x=x_vals,
            marker_color=entity_color[ent],
            legendgroup=ent,
            hovertemplate=(
                '<b>%{y}</b><br>'
                'Entidad: ' + ent + '<br>'
                'Deuda: $%{x:,.0f}<br>'
                '<extra></extra>'
            ),
        ))

    return traces, df_top

# ── Generar los 5 gráficos individuales ─────────────────────────────────────
for sit in ['1', '2', '3', '4', '5']:
    traces, df_top = build_stacked_bar(sit)

    fig = go.Figure(traces)
    fig.update_layout(
        barmode='stack',
        title=dict(
            text=(f'<b>Top 10 Deudores Jurídicos por Deuda Total</b><br>'
                  f'<sup>{sit_labels[sit]} · Febrero 2026 · BCRA</sup>'),
            x=0.5, font=dict(size=15),
        ),
        xaxis=dict(title='Deuda total en préstamos ($)', tickformat=',.0f',
                   gridcolor='#e5e7eb'),
        yaxis=dict(automargin=True),
        legend=dict(title='Entidad Financiera', font=dict(size=9)),
        height=420,
        plot_bgcolor='white',
        paper_bgcolor='#f9fafb',
        margin=dict(l=20, r=20, t=80, b=40),
    )
    fig.show()

# ── Exportar JSON para la web ────────────────────────────────────────────────
# Formato: por situacion → lista de {cuit, denominacion, deuda_total, entidades:[{nombre, monto}]}
chart_data = {}
for sit in ['1', '2', '3', '4', '5']:
    df_top = tops[sit]
    df_det = details[sit]
    result = []
    for _, row in df_top.iterrows():
        ents = (df_det[df_det['nro_id'] == row['nro_id']]
                [['nombre_entidad', 'deuda_entidad']]
                .sort_values('deuda_entidad', ascending=False)
                .rename(columns={'nombre_entidad': 'entidad', 'deuda_entidad': 'monto'})
                .to_dict('records'))
        result.append({
            'cuit':        row['nro_id'],
            'denominacion': row['denominacion'],
            'deuda_total':  float(row['deuda_total']),
            'entidades':    ents,
        })
    chart_data[sit] = result

json_path = '/content/drive/MyDrive/Tesis2026/chart_data_v2.json'
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(chart_data, f, ensure_ascii=False, indent=2)

print(f"\n✅ JSON exportado → {json_path}")
print("\nResumen:")
for sit in ['1','2','3','4','5']:
    total = sum(r['deuda_total'] for r in chart_data[sit])
    n_ents = len({e['entidad'] for r in chart_data[sit] for e in r['entidades']})
    print(f"  Sit {sit}: {len(chart_data[sit])} deudores · "
          f"{n_ents} entidades distintas · Deuda top-10: ${total:,.0f}")

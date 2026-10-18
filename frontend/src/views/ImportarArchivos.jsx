import EscanearHorario from './EscanearHorario.jsx'

export default function ImportarArchivos() {
  return <>
    <div className="page-heading">
      <div>
        <h2>Importar archivo</h2>
        <p>Un solo espacio para analizar horarios Excel, CSV e imágenes y revisar los datos antes de registrarlos.</p>
      </div>
    </div>
    <EscanearHorario embedded />
  </>
}

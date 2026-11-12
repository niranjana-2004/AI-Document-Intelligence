import { FileSearch } from 'lucide-react'
import { getFactTypeMeta } from '../../utils/researchPaperUtils'

export default function PaperSectionCard({
    title,
    subtitle,
    icon: Icon,
    sectionData,
    fieldDefinitions,
    onInspectField,
}) {
    if (!sectionData) return null

    const populatedCount = fieldDefinitions.filter(
        ({ key }) => sectionData[key] && sectionData[key].fact_type !== 'missing'
    ).length

    return (
        <article className="rpa-section-card">
            <header className="rpa-section-header">
                <div className="rpa-section-title-group">
                    {Icon && (
                        <span className="rpa-section-icon">
                            <Icon size={17} />
                        </span>
                    )}
                    <div>
                        <h3>{title}</h3>
                        {subtitle && <p>{subtitle}</p>}
                    </div>
                </div>
                <span className="rpa-section-count">
                    {populatedCount}/{fieldDefinitions.length} grounded
                </span>
            </header>

            <div className="rpa-field-list">
                {fieldDefinitions.map(({ key, label }) => {
                    const field = sectionData[key]
                    if (!field) return null
                    const isMissing = field.fact_type === 'missing'
                    const meta = getFactTypeMeta(field.fact_type)
                    const sources = Array.isArray(field.sources) ? field.sources : []

                    return (
                        <div key={key} className={`rpa-field-row ${isMissing ? 'is-missing' : ''}`}>
                            <div className="rpa-field-head">
                                <span className="rpa-field-label">{label}</span>
                                <div className="rpa-field-badges">
                                    <span className={`rpa-fact-chip tone-${meta.tone}`} title={meta.description}>
                                        {meta.label}
                                    </span>
                                    {!isMissing && typeof field.confidence === 'number' && (
                                        <span className="rpa-conf-pill">
                                            {Math.round(field.confidence * 100)}%
                                        </span>
                                    )}
                                </div>
                            </div>

                            <p className="rpa-field-value">{field.value}</p>

                            {sources.length > 0 && (
                                <div className="rpa-field-actions">
                                    <button
                                        type="button"
                                        className="rpa-source-trigger"
                                        onClick={() => onInspectField(label, field)}
                                    >
                                        <FileSearch size={13} />
                                        <span>
                                            Verify on p.{sources[0].page}
                                            {sources[0].section ? ` · ${sources[0].section}` : ''}
                                            {sources.length > 1 ? ` (+${sources.length - 1})` : ''}
                                        </span>
                                    </button>
                                </div>
                            )}
                        </div>
                    )
                })}
            </div>
        </article>
    )
}


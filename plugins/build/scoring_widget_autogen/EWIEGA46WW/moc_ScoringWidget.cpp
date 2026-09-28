/****************************************************************************
** Meta object code from reading C++ file 'ScoringWidget.hh'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "../../../ScoringWidget.hh"
#include <QScreen>
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'ScoringWidget.hh' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 68
#error "This file was generated using the moc from 6.4.2. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

#ifndef Q_CONSTINIT
#define Q_CONSTINIT
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
namespace {
struct qt_meta_stringdata_regatta__ScoringWidget_t {
    uint offsetsAndSizes[26];
    char stringdata0[23];
    char stringdata1[12];
    char stringdata2[1];
    char stringdata3[11];
    char stringdata4[9];
    char stringdata5[13];
    char stringdata6[8];
    char stringdata7[8];
    char stringdata8[13];
    char stringdata9[11];
    char stringdata10[11];
    char stringdata11[11];
    char stringdata12[14];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_regatta__ScoringWidget_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_regatta__ScoringWidget_t qt_meta_stringdata_regatta__ScoringWidget = {
    {
        QT_MOC_LITERAL(0, 22),  // "regatta::ScoringWidget"
        QT_MOC_LITERAL(23, 11),  // "DataChanged"
        QT_MOC_LITERAL(35, 0),  // ""
        QT_MOC_LITERAL(36, 10),  // "totalScore"
        QT_MOC_LITERAL(47, 8),  // "maxScore"
        QT_MOC_LITERAL(56, 12),  // "scorePercent"
        QT_MOC_LITERAL(69, 7),  // "simTime"
        QT_MOC_LITERAL(77, 7),  // "timeout"
        QT_MOC_LITERAL(85, 12),  // "clearedCount"
        QT_MOC_LITERAL(98, 10),  // "totalCount"
        QT_MOC_LITERAL(109, 10),  // "statusText"
        QT_MOC_LITERAL(120, 10),  // "isFinished"
        QT_MOC_LITERAL(131, 13)   // "waypointsList"
    },
    "regatta::ScoringWidget",
    "DataChanged",
    "",
    "totalScore",
    "maxScore",
    "scorePercent",
    "simTime",
    "timeout",
    "clearedCount",
    "totalCount",
    "statusText",
    "isFinished",
    "waypointsList"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_regatta__ScoringWidget[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       1,   14, // methods
      10,   21, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       1,       // signalCount

 // signals: name, argc, parameters, tag, flags, initial metatype offsets
       1,    0,   20,    2, 0x06,   11 /* Public */,

 // signals: parameters
    QMetaType::Void,

 // properties: name, type, flags
       3, QMetaType::Double, 0x00015001, uint(0), 0,
       4, QMetaType::Double, 0x00015001, uint(0), 0,
       5, QMetaType::Double, 0x00015001, uint(0), 0,
       6, QMetaType::Double, 0x00015001, uint(0), 0,
       7, QMetaType::Double, 0x00015001, uint(0), 0,
       8, QMetaType::Int, 0x00015001, uint(0), 0,
       9, QMetaType::Int, 0x00015001, uint(0), 0,
      10, QMetaType::QString, 0x00015001, uint(0), 0,
      11, QMetaType::Bool, 0x00015001, uint(0), 0,
      12, QMetaType::QVariantList, 0x00015001, uint(0), 0,

       0        // eod
};

Q_CONSTINIT const QMetaObject regatta::ScoringWidget::staticMetaObject = { {
    QMetaObject::SuperData::link<gz::gui::Plugin::staticMetaObject>(),
    qt_meta_stringdata_regatta__ScoringWidget.offsetsAndSizes,
    qt_meta_data_regatta__ScoringWidget,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_regatta__ScoringWidget_t,
        // property 'totalScore'
        QtPrivate::TypeAndForceComplete<double, std::true_type>,
        // property 'maxScore'
        QtPrivate::TypeAndForceComplete<double, std::true_type>,
        // property 'scorePercent'
        QtPrivate::TypeAndForceComplete<double, std::true_type>,
        // property 'simTime'
        QtPrivate::TypeAndForceComplete<double, std::true_type>,
        // property 'timeout'
        QtPrivate::TypeAndForceComplete<double, std::true_type>,
        // property 'clearedCount'
        QtPrivate::TypeAndForceComplete<int, std::true_type>,
        // property 'totalCount'
        QtPrivate::TypeAndForceComplete<int, std::true_type>,
        // property 'statusText'
        QtPrivate::TypeAndForceComplete<QString, std::true_type>,
        // property 'isFinished'
        QtPrivate::TypeAndForceComplete<bool, std::true_type>,
        // property 'waypointsList'
        QtPrivate::TypeAndForceComplete<QVariantList, std::true_type>,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<ScoringWidget, std::true_type>,
        // method 'DataChanged'
        QtPrivate::TypeAndForceComplete<void, std::false_type>
    >,
    nullptr
} };

void regatta::ScoringWidget::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<ScoringWidget *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->DataChanged(); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (ScoringWidget::*)();
            if (_t _q_method = &ScoringWidget::DataChanged; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 0;
                return;
            }
        }
    }else if (_c == QMetaObject::ReadProperty) {
        auto *_t = static_cast<ScoringWidget *>(_o);
        (void)_t;
        void *_v = _a[0];
        switch (_id) {
        case 0: *reinterpret_cast< double*>(_v) = _t->TotalScore(); break;
        case 1: *reinterpret_cast< double*>(_v) = _t->MaxScore(); break;
        case 2: *reinterpret_cast< double*>(_v) = _t->ScorePercent(); break;
        case 3: *reinterpret_cast< double*>(_v) = _t->SimTime(); break;
        case 4: *reinterpret_cast< double*>(_v) = _t->Timeout(); break;
        case 5: *reinterpret_cast< int*>(_v) = _t->ClearedCount(); break;
        case 6: *reinterpret_cast< int*>(_v) = _t->TotalCount(); break;
        case 7: *reinterpret_cast< QString*>(_v) = _t->StatusText(); break;
        case 8: *reinterpret_cast< bool*>(_v) = _t->IsFinished(); break;
        case 9: *reinterpret_cast< QVariantList*>(_v) = _t->WaypointsList(); break;
        default: break;
        }
    } else if (_c == QMetaObject::WriteProperty) {
    } else if (_c == QMetaObject::ResetProperty) {
    } else if (_c == QMetaObject::BindableProperty) {
    }
    (void)_a;
}

const QMetaObject *regatta::ScoringWidget::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *regatta::ScoringWidget::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_regatta__ScoringWidget.stringdata0))
        return static_cast<void*>(this);
    return gz::gui::Plugin::qt_metacast(_clname);
}

int regatta::ScoringWidget::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = gz::gui::Plugin::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 1)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 1;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 1)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 1;
    }else if (_c == QMetaObject::ReadProperty || _c == QMetaObject::WriteProperty
            || _c == QMetaObject::ResetProperty || _c == QMetaObject::BindableProperty
            || _c == QMetaObject::RegisterPropertyMetaType) {
        qt_static_metacall(this, _c, _id, _a);
        _id -= 10;
    }
    return _id;
}

// SIGNAL 0
void regatta::ScoringWidget::DataChanged()
{
    QMetaObject::activate(this, &staticMetaObject, 0, nullptr);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE

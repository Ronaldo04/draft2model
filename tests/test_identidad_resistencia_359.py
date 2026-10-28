"""Una nota compartida no convierte fy/f'm en resistencia del concreto."""
import unittest
from draft2model.preparacion_configuracion import lecturas_tecnicas


class IdentidadResistenciaTests(unittest.TestCase):
    def row(self,id,symbol,value,text="f'c=210 kgf/cm2; fy=4200 kgf/cm2; f'm=45 kgf/cm2"):
        return {'id':id,'tipo':'propiedad','valor_propuesto':value,'unidad':'kgf/cm2',
                'texto_fuente':text,'simbolo':symbol,'evidencia':[], 'revision':{'estado':'pendiente','historial':[]}}

    def test_simbolo_distingue_tres_valores_de_misma_evidencia(self):
        rows=[self.row('CONCRETO',"f'c",210),self.row('ACERO','fy',4200),self.row('ALBANILERIA',"f'm",45)]
        result=lecturas_tecnicas({'candidatos':rows})
        self.assertEqual([r['id'] for r in result if r['resistencia_concreto']],['CONCRETO'])

    def test_sin_simbolo_un_bloque_ambiguo_requiere_revision(self):
        row=self.row('AMBIGUO','',4200)
        self.assertFalse(lecturas_tecnicas({'candidatos':[row]})[0]['resistencia_concreto'])
        row['texto_fuente']="f'c=210 kgf/cm2";row['valor_propuesto']=210
        self.assertTrue(lecturas_tecnicas({'candidatos':[row]})[0]['resistencia_concreto'])

    def test_simbolo_sin_literal_coherente_no_basta(self):
        row=self.row('INCOHERENTE',"f'c",4200,'fy=4200 kgf/cm2')
        self.assertFalse(lecturas_tecnicas({'candidatos':[row]})[0]['resistencia_concreto'])


if __name__=='__main__':unittest.main()

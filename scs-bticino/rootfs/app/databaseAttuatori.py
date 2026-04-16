#!/usr/bin/env python3
from tinydb import TinyDB, Query
import os


# tinydb
# https://pypi.org/project/tinydb/#example-code
# https://github.com/msiemens/tinydb

"""
Struttura database

nome attuatore - tipo attuatore - indirizzo Ambiente - indirizzo PL
"""

DB_PATH = '/data/scs_database.json'


class configurazione_database:
    def __init__(self):
        # print(self.db.all())
        db_dir = os.path.dirname(DB_PATH)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        self.db = TinyDB(DB_PATH)

    def _normalizza_nome_attuatore(self, nome_attuatore):
        if isinstance(nome_attuatore, str):
            nome_attuatore = nome_attuatore.strip().lower()
            if nome_attuatore:
                return nome_attuatore
        return None

    def _filtro_nome_attuatore(self, nome_attuatore):
        nome_attuatore_normalizzato = self._normalizza_nome_attuatore(nome_attuatore)
        if nome_attuatore_normalizzato is None:
            return None

        UUID = Query()
        return UUID.nome_attuatore.test(
            lambda x: isinstance(x, str) and x.strip().lower() == nome_attuatore_normalizzato
        )

    def CHECHK_ESISTE_ATTUATORE(self, nome_attuatore):
        filtro = self._filtro_nome_attuatore(nome_attuatore)
        if filtro is None:
            return False

        val = self.db.search(filtro)
        return len(val) > 0

    def AGGIUNGI_ATTUATORE(self, nome_attuatore, tipo_attuatore, indirizzo_Ambiente, indirizzo_PL):
        nome_attuatore = self._normalizza_nome_attuatore(nome_attuatore)
        if nome_attuatore is None:
            return False

        filtro = self._filtro_nome_attuatore(nome_attuatore)
        if not self.CHECHK_ESISTE_ATTUATORE(nome_attuatore):
            self.db.insert({
                'nome_attuatore': nome_attuatore,
                'tipo_attuatore': tipo_attuatore,
                'indirizzo_Ambiente': indirizzo_Ambiente,
                'indirizzo_PL': indirizzo_PL
            })
        else:
            self.db.update({
                'nome_attuatore': nome_attuatore,
                'tipo_attuatore': tipo_attuatore,
                'indirizzo_Ambiente': indirizzo_Ambiente,
                'indirizzo_PL': indirizzo_PL
            }, filtro)

        return True

    def AGGIORNA_ATTUATORE_xNome(self, nome_attuatore, nuovo_attuatore):
        filtro = self._filtro_nome_attuatore(nome_attuatore)
        nuovo_attuatore = self._normalizza_nome_attuatore(nuovo_attuatore)

        if filtro is not None and nuovo_attuatore is not None:
            if self.CHECHK_ESISTE_ATTUATORE(nome_attuatore):
                if not self.CHECHK_ESISTE_ATTUATORE(nuovo_attuatore):
                    self.db.update({'nome_attuatore': nuovo_attuatore}, filtro)

    def AGGIORNA_ATTUATORE_xTipo(self, nome_attuatore, tipo_attuatore):
        filtro = self._filtro_nome_attuatore(nome_attuatore)
        if filtro is not None and self.CHECHK_ESISTE_ATTUATORE(nome_attuatore):
            self.db.update({'tipo_attuatore': tipo_attuatore}, filtro)

    def AGGIORNA_ATTUATORE_xindirizzo_Ambiente(self, nome_attuatore, indirizzo_Ambiente):
        filtro = self._filtro_nome_attuatore(nome_attuatore)
        if filtro is not None and self.CHECHK_ESISTE_ATTUATORE(nome_attuatore):
            self.db.update({'indirizzo_Ambiente': indirizzo_Ambiente}, filtro)

    def AGGIORNA_ATTUATORE_xindirizzo_PL(self, nome_attuatore, indirizzo_PL):
        filtro = self._filtro_nome_attuatore(nome_attuatore)
        if filtro is not None and self.CHECHK_ESISTE_ATTUATORE(nome_attuatore):
            self.db.update({'indirizzo_PL': indirizzo_PL}, filtro)

    def AGGIORNA_TIMER_SERRANDETAPPARELLE_UP(self, nome_attuatore, timer_salita):
        filtro = self._filtro_nome_attuatore(nome_attuatore)
        if filtro is not None and self.CHECHK_ESISTE_ATTUATORE(nome_attuatore):
            self.db.update({'timer_salita': timer_salita}, filtro)

    def AGGIORNA_TIMER_SERRANDETAPPARELLE_DW(self, nome_attuatore, timer_discesa):
        filtro = self._filtro_nome_attuatore(nome_attuatore)
        if filtro is not None and self.CHECHK_ESISTE_ATTUATORE(nome_attuatore):
            self.db.update({'timer_discesa': timer_discesa}, filtro)

    def AGGIORNA_ATTUATORE_x_AWS_ENDPOINT(self, nome_attuatore, nome_endpoint):
        filtro = self._filtro_nome_attuatore(nome_attuatore)
        if filtro is not None and self.CHECHK_ESISTE_ATTUATORE(nome_attuatore):
            self.db.update({'nome_endpoint': nome_endpoint}, filtro)

    def RICHIESTA_ATTUATORE(self, nome_attuatore):
        filtro = self._filtro_nome_attuatore(nome_attuatore)
        if filtro is not None and self.CHECHK_ESISTE_ATTUATORE(nome_attuatore):
            val = self.db.search(filtro)
            if len(val) > 0:
                return val[0]
        return None

    def RICHIESTA_TUTTI_ATTUATORI(self):
        query = self.db.all()

        query_validi = [
            q for q in query
            if q.get('nome_attuatore') is not None and str(q.get('nome_attuatore')).strip() != ''
        ]

        all_att = sorted(
            query_validi,
            key=lambda q: str(q.get('nome_attuatore', '')).lower()
        )

        ordine_x_tipo = [
            'on_off', 'dimmer', 'serrande_tapparelle', 'sensori_temperatura',
            'termostati', 'serrature', 'campanello_porta', 'gruppi'
        ]

        all_attuatori = []
        for ord_tipo in ordine_x_tipo:
            for q in all_att:
                if q.get('tipo_attuatore') == ord_tipo:
                    all_attuatori.append(q)

        for q in all_att:
            if q.get('tipo_attuatore') not in ordine_x_tipo:
                all_attuatori.append(q)

        return all_attuatori

    def RIMUOVE_ATTUATORE(self, nome_attuatore):
        filtro = self._filtro_nome_attuatore(nome_attuatore)
        if filtro is not None and self.CHECHK_ESISTE_ATTUATORE(nome_attuatore):
            self.db.remove(filtro)

    def myprint(self):
        # self.db.purge()
        # print(self.db.all())
        # print(len(self.db))
        pass


if __name__ == "__main__":
    dbm = configurazione_database()
    va = dbm.RICHIESTA_ATTUATORE('mvhjm')
    print(va)

    try:
        print(va['nome_atstuatore'])
    except KeyError:
        print("Non ha il nome")
        pass

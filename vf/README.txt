#Pour créer le .exe :

python -m PyInstaller --onefile --noconsole main.py --hidden-import=dearpygui.dearpygui
-> à partir du .exe (dans le dossier dist) créer tu peux faire un raccourci pour l'avoir sur le bureau 
Si jamais ton code à besoin de dossier complémentatire, copie les dans dist

pour les librairies :
(pas besoin si t'as le .exe, c'est surtout pour modifier le code)

Créer environnement :
python -m venv myenv
L'activer :
myenv\Scripts\activate

-----Pour garder toutes les librairies utilisées avec leurs versions----
créer un fichier requirements.txt dans le même dossier que là ou s'est placer myenv :
dossier -myenv
        -requirements.txt
Sauvegarder toute les librairies installées
pip freeze > requirements.txt

Il faudra juste garder le requirements.txt !

-----Pour installer les librairies présentes dans requirements.txt----
pip install -r requirements.txt

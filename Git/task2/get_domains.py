# !/usr/bin/env python3

import requests
import json
import time
from collections import Counter
from typing import Dict, List, Set, Optional

def find_best_cell_line():
    """Найти клеточную линию с наибольшим количеством DNase-seq экспериментов."""
    print("Finding cell line with most DNase-seq experiments...")
    
    base_url = "https://www.encodeproject.org/search/"
    
    # Получаем все DNase-seq эксперименты на cell lines
    params = {
        "type": "Experiment",
        "assay_title": "DNase-seq",
        "status": "released",
        "biosample_ontology.classification": "cell line",
        "format": "json"
    }
    
    response = requests.get(base_url, params=params)
    data = response.json()
    
    #Считаем количество экспериментов на клеточную линию
    cell_line_counts = Counter()
    for exp in data.get('@graph', []):
        if 'biosample_ontology' in exp and 'term_name' in exp['biosample_ontology']:
            cell_line = exp['biosample_ontology']['term_name']
            cell_line_counts[cell_line] += 1
    
    if not cell_line_counts:
        raise Exception("No DNase-seq experiments found")
    
    # Находим топ-1 клеточную линию
    top_cell_line, max_count = cell_line_counts.most_common(1)[0]
    print(f"Top cell line: {top_cell_line} ({max_count} DNase-seq experiments)")
    return top_cell_line


def get_tf_proteins_for_cell_line(cell_line: str) -> List[str]:
    #Получить список генов транскрипционных факторов для данной клеточной линии.
    print(f"\n Getting TF ChIP-seq proteins for {cell_line}...")
    
    base_url = "https://www.encodeproject.org/search/"
    params = {
        "type": "Experiment",
        "assay_title": "TF ChIP-seq",
        "status": "released",
        "biosample_ontology.term_name": cell_line,
        "format": "json"
    }
    
    response = requests.get(base_url, params=params)
    data = response.json()
    
    #Собираем уникальные гены
    genes = set()
    for exp in data.get('@graph', []):
        if 'target' in exp and 'label' in exp['target']:
            genes.add(exp['target']['label'])
    
    print(f"Found {len(genes)} unique TF proteins")
    return list(genes)


#  UniProt API 
def map_gene_to_uniprot(gene_symbols: List[str]) -> Dict[str, Optional[str]]:
  
    print(f"\n Mapping {len(gene_symbols)} gene symbols to UniProt IDs...")
    
    uniprot_url = "https://rest.uniprot.org/uniprotkb/search"
    mapping = {}
    
    for i, gene in enumerate(gene_symbols, 1):
        #Ищем по точному названию гена и организму человек 
        params = {
            "query": f"gene_exact:{gene} AND organism_id:9606",
            "fields": "accession,gene_names",
            "format": "json",
            "size": 1
        }
        
        try:
            response = requests.get(uniprot_url, params=params, timeout=10)
            data = response.json()
            
            if data.get('results'):
                uniprot_id = data['results'][0]['primaryAccession']
                mapping[gene] = uniprot_id
                print(f"[{i}/{len(gene_symbols)}] {gene} → {uniprot_id}")
            else:
                mapping[gene] = None
                print(f"[{i}/{len(gene_symbols)}] {gene} - not found")
                
            #задержка между запросами
            time.sleep(0.3)
            
        except Exception as e:
            print(f"Error for {gene}: {e}")
            mapping[gene] = None
    
    found = sum(1 for v in mapping.values() if v is not None)
    print(f"Successfully mapped {found}/{len(gene_symbols)} genes")
    return mapping


#InterPro API (Pfam) 
def get_pfam_domains(uniprot_id: str) -> List[str]:
    """
    Получить Pfam домены для белка через InterPro API.
    """
    # Первый запрос: получаем metadata с entries_url
    url = f"https://www.ebi.ac.uk/interpro/api/protein/uniprot/{uniprot_id}/entry/pfam"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        
        # Извлекаем entries_url (ссылка на список доменов)
        entries_url = data.get('entries_url')
        if not entries_url:
            return []
        
        # Второй запрос: получаем список Pfam записей
        response2 = requests.get(entries_url, timeout=10)
        if response2.status_code != 200:
            return []
        
        data2 = response2.json()
        domains = []
        
        # Теперь data2 содержит results
        results = data2.get('results', [])
        
        for entry in results:
            metadata = entry.get('metadata', {})
            domain_name = metadata.get('name')
            
            if not domain_name:
                domain_name = metadata.get('accession')
            
            if domain_name:
                domains.append(domain_name)
        
        return list(set(domains))
        
    except Exception as e:
        print(f"   Error for {uniprot_id}: {e}")
        return []

def get_all_domains(protein_uniprot_map: Dict[str, Optional[str]]) -> Dict[str, List[str]]:
    #Получить домены для всех успешно смапленных белков.
    print(f"\n Fetching Pfam domains from InterPro API...")
    
    domains_dict = {}
    
    for gene, uniprot_id in protein_uniprot_map.items():
        if uniprot_id is None:
            domains_dict[gene] = []
            continue
            
        print(f"Fetching domains for {gene} ({uniprot_id})...")
        domains = get_pfam_domains(uniprot_id)
        domains_dict[gene] = domains
        print(f"Found {len(domains)} Pfam domains: {', '.join(domains[:5])}" + 
              (f"..." if len(domains) > 5 else ""))
        
        time.sleep(0.3)  
    
    return domains_dict


def main():
    print("ENCODE → UniProt → InterPro Pipeline")
    
    #ENCODE
    top_cell_line = find_best_cell_line()
    tf_genes = get_tf_proteins_for_cell_line(top_cell_line)
    
    #UniProt маппинг
    gene_to_uniprot = map_gene_to_uniprot(tf_genes)
    
    #InterPro (Pfam) домены
    domains_result = get_all_domains(gene_to_uniprot)
    
    #Сохраняем результат
    output_file = "domains.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(domains_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n Results saved to {output_file}")
    
    #Статистика
    total_with_domains = sum(1 for d in domains_result.values() if d)
    total_domains = sum(len(d) for d in domains_result.values())
    print(f"Statistics:")
    print(f"   - Top cell line: {top_cell_line}")
    print(f"   - TF proteins found: {len(tf_genes)}")
    print(f"   - Mapped to UniProt: {sum(1 for v in gene_to_uniprot.values() if v)}")
    print(f"   - Proteins with domains: {total_with_domains}")
    print(f"   - Total Pfam domains found: {total_domains}")


if __name__ == "__main__":
    main()

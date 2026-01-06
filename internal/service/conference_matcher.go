package service

import (
	"regexp"
	"strings"
)

// ConferenceMatcher 会议/期刊匹配器
type ConferenceMatcher struct {
	patterns map[string][]*regexp.Regexp
	topTier  map[string]bool
}

// NewConferenceMatcher 创建会议匹配器
func NewConferenceMatcher() *ConferenceMatcher {
	cm := &ConferenceMatcher{
		patterns: make(map[string][]*regexp.Regexp),
		topTier:  make(map[string]bool),
	}
	cm.initPatterns()
	return cm
}

// 全局单例
var defaultMatcher = NewConferenceMatcher()

// MatchConference 匹配会议名称
func MatchConference(venue string) string {
	return defaultMatcher.Match(venue)
}

// IsTopTierVenue 判断是否是顶会/顶刊
func IsTopTierVenue(venue string) bool {
	return defaultMatcher.topTier[venue]
}

// Match 匹配并返回标准化的会议/期刊名称
func (cm *ConferenceMatcher) Match(venue string) string {
	if venue == "" {
		return ""
	}

	// 清理特殊字符
	venue = strings.TrimSpace(venue)
	venue = strings.ReplaceAll(venue, "\u00a0", " ")
	venue = strings.ReplaceAll(venue, "–", "-")
	venue = strings.ReplaceAll(venue, "—", "-")

	// 遍历所有模式
	for name, patterns := range cm.patterns {
		for _, pattern := range patterns {
			if pattern.MatchString(venue) {
				return name
			}
		}
	}

	return venue
}

func (cm *ConferenceMatcher) initPatterns() {
	// 定义所有模式
	patternDefs := map[string][]string{
		// ==================== AI & ML ====================
		"NeurIPS": {
			`(?i)neural information processing systems?`,
			`(?i)proceedings of (?:the\s+)?neural information processing systems`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference on neural information processing systems?`,
			`(?i)^neurips(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)neurips['\"]?\d{2}`,
			`(?i)\[neurips['\"]?\d{2}\]`,
			`(?i)neurips.*\d{4}`,
			`(?i)advances in neural information processing systems \d+`,
			`(?i)advances in neural information processing systems.*\d{4}`,
			`(?i)nips`,
		},
		"ICML": {
			`(?i)international conference on machine learning`,
			`(?i)proceedings of (?:the\s+)?international conference on machine learning`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?international conference on machine learning`,
			`(?i)^icml(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)icml['\"]?\d{2}`,
			`(?i)\[icml['\"]?\d{2}\]`,
			`(?i)icml.*\d{4}.*(?:best\s+paper)?`,
		},
		"ICLR": {
			`(?i)international conference on learning representations`,
			`(?i)proceedings of (?:the\s+)?international conference on learning representations`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?international conference on learning representations`,
			`(?i)^iclr(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)iclr['\"]?\d{2}`,
			`(?i)\[iclr['\"]?\d{2}\]`,
			`(?i)iclr.*\d{4}`,
		},
		"AAAI": {
			`(?i)association for the advancement of artificial intelligence`,
			`(?i)proceedings of the aaai conference on artificial intelligence`,
			`(?i)(?:the\s+)?(?:\d+(?:st|nd|rd|th)|\w+(?:-\w+)?)\s*aaai conference`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?aaai conference`,
			`(?i)aaai conference on artificial intelligence.*\d{4}`,
			`(?i)^aaai(?:\s*-\s*\d{2})?(?:\s+\d{4})?$`,
			`(?i)^aaai(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},
		"IJCAI": {
			`(?i)international joint conference(?:s)? on artificial intelligence`,
			`(?i)proceedings of the (?:\d+(?:st|nd|rd|th)|\w+)(?:\s*-\s*\w+)?\s*international joint conference`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?ijcai`,
			`(?i)^ijcai(?:\s*\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},
		"AAMAS": {
			`(?i)international conference on autonomous agents and multiagent systems?`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?aamas`,
			`(?i)^aamas(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)^aamas(?:\s+\d{4})?$`,
		},

		// ==================== Computer Vision ====================
		"CVPR": {
			`(?i)conference on computer vision and pattern recognition`,
			`(?i)computer vision and pattern recognition conference`,
			`(?i)ieee/cvf\s*conference on computer vision and pattern recognition`,
			`(?i)proceedings of (?:the\s+)?(?:ieee(?:/cvf)?\s*)?conference on computer vision and pattern`,
			`(?i)proceedings of (?:the\s+)?computer vision and pattern recognition conference`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference on computer vision and pattern recognition`,
			`(?i)^cvpr(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)cvpr['\"]?\d{2}`,
			`(?i)\[cvpr['\"]?\d{2}\]`,
			`(?i)cvpr.*\d{4}`,
		},
		"ICCV": {
			`(?i)international conference on computer vision`,
			`(?i)ieee/cvf.*international conference on computer vision`,
			`(?i)proceedings of the (?:ieee(?:/cvf)?\s*)?international conference on computer vision`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?international conference on computer vision`,
			`(?i)^iccv(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)iccv['\"]?\d{2}`,
			`(?i)\[iccv['\"]?\d{2}\]`,
			`(?i)iccv.*\d{4}`,
		},
		"ECCV": {
			`(?i)european conference on computer vision`,
			`(?i)computer vision[\s\-–—]+eccv\s*\d{4}`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?european conference on computer vision`,
			`(?i)eccv\s*\d{4}.*(?:conference|glasgow)`,
			`(?i)^eccv(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},
		"3DV": {
			`(?i)international conference (?:in|on) 3d vision`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:international\s*)?3dv`,
			`(?i)^3dv(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)3dv['\"]?\d{2}`,
		},
		"ACM MM": {
			`(?i)acm international conference on multimedia`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?acm (?:international )?conference on multimedia`,
			`(?i)^acm\s*mm(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)acm\s*mm.*\d{4}`,
			`(?i)^mm(?:\s+\d{4})?$`,
		},
		"SIGGRAPH Asia": {
			`(?i)siggraph\s+asia(?:\s+\d{4})?(?:\s+conference\s+papers)?`,
			`(?i)acm\s+siggraph\s+asia(?:\s+\d{4})?`,
			`(?i)^siggraph\s+asia(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},
		"SIGGRAPH": {
			`(?i)siggraph(?:\s+\d{4})?(?:\s+conference\s+papers)?`,
			`(?i)acm\s+siggraph(?:\s+\d{4})?`,
			`(?i)^siggraph(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},

		// ==================== NLP ====================
		"ACL Findings": {
			`(?i)findings\s+of\s+(?:the\s+)?\s*acl`,
			`(?i)findings\s+of\s+(?:the\s+)?\s*acl\s+\d{4}(?:\s*,\s*\d{4})?`,
			`(?i)acl\s+findings`,
		},
		"EMNLP Findings": {
			`(?i)findings\s+of\s+(?:the\s+)?\s*emnlp`,
			`(?i)findings\s+of\s+(?:the\s+)?\s*emnlp\s+\d{4}(?:\s*,\s*\d{4})?`,
			`(?i)emnlp\s+findings`,
		},
		"ACL": {
			`(?i)association for computational linguistics`,
			`(?i)proceedings of (?:the\s+)?association for computational linguistics`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?meeting of the acl`,
			`(?i)^acl(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)acl['\"]?\d{2}`,
			`(?i)\[acl['\"]?\d{2}\]`,
			`(?i)acl.*\d{4}`,
		},
		"EMNLP": {
			`(?i)conference on empirical methods in natural language processing`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference on empirical methods in nlp`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference on empirical methods in natural language`,
			`(?i)^emnlp(?:\s+\d{4})?(?:\s*,\s*\d{4})?$`,
			`(?i)emnlp\s+\d{4}`,
		},
		"NAACL": {
			`(?i)north american chapter of the association for computational linguistics`,
			`(?i)proceedings of the (?:\d{4}\s+)?conference of the north american chapter`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference of the naacl`,
			`(?i)naacl(?:\s*-\s*\w+)?(?:\s+\d{4})?`,
			`(?i)^naacl(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},
		"COLM": {
			`(?i)conference on online learning and meta-learning`,
			`(?i)colm[\s\-]+\d{4}(?:\s+oral)?(?:\s*,\s*\d{4})?`,
			`(?i)colm.*\d{4}.*oral(?:\s*,\s*\d{4})?`,
			`(?i)colm\s+\d{4}(?:\s+oral)?(?:\s*, \s*\d{4})?`,
		},

		// ==================== Data Mining & Databases ====================
		"KDD": {
			`(?i)knowledge discovery and data mining`,
			`(?i)proceedings of (?:the\s+)?(?:\d+(?:st|nd|rd|th)?\s*)?acm sigkdd`,
			`(?i)acm sigkdd international conference`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?conference on kdd`,
			`(?i)^kdd(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)kdd['\"]?\d{2}`,
			`(?i)\[kdd['\"]?\d{2}\]`,
			`(?i)kdd.*\d{4}`,
		},
		"SIGMOD": {
			`(?i)international conference on management of data`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?sigmod`,
			`(?i)^sigmod(?:\s+\d{4})?$`,
		},
		"VLDB": {
			`(?i)very large data bases`,
			`(?i)international conference on very large data bases`,
			`(?i)proceedings of the vldb endowment`,
			`(?i)^vldb(?:\s+\d{4})?$`,
			`(?i)vldb.*endowment.*\d{4}`,
		},
		"WWW": {
			`(?i)international world wide web conferences?`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?international www conference`,
			`(?i)^www(?:\s+\d{4})?$`,
			`(?i)world wide web conference`,
			`(?i)international conference companion on world wide web`,
			`(?i)companion proceedings of the.*world wide web conference`,
		},
		"SIGIR": {
			`(?i)international conference on research (?:and development )?in information retrieval`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?sigir`,
			`(?i)international acm sigir conference`,
			`(?i)^sigir(?:\s+\d{4})?$`,
		},
		"ICDE": {
			`(?i)international conference on data engineering`,
			`(?i)ieee.*international conference on data engineering.*icde`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?icde`,
			`(?i)^icde(?:\s+\d{4})?$`,
		},

		// ==================== Security ====================
		"CCS": {
			`(?i)conference on computer and communications security`,
			`(?i)acm sigsac conference on computer and communications`,
			`(?i)proceedings of (?:the\s+)?(?:\d{4}\s*)?acm sigsac`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?acm ccs`,
			`(?i)^ccs(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)ccs['\"]?\d{2}`,
			`(?i)\[ccs['\"]?\d{2}\]`,
			`(?i)ccs.*\d{4}`,
		},
		"USENIX Security": {
			`(?i)usenix security symposium`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?usenix security`,
			`(?i)^usenix(?:\s+security)?(?:\s+\d{4})?$`,
		},
		"NDSS": {
			`(?i)network and distributed system security symposium`,
			`(?i)network and distributed system security symposium.*ndss`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?ndss`,
			`(?i)^ndss(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},
		"S&P": {
			`(?i)symposium on security and privacy`,
			`(?i)ieee.*symposium on security and privacy.*s&p`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee\s*)?s(?:&|and)p`,
			`(?i)^s(?:&|and)p(?:['\s]+\d{2,4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},

		// ==================== Systems ====================
		"OSDI": {
			`(?i)symposium on operating systems design and implementation`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:usenix\s*)?symposium on operating systems design`,
			`(?i)usenix.*osdi`,
			`(?i)^osdi(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)osdi\s+\d{4}`,
		},
		"NSDI": {
			`(?i)symposium on networked systems design and implementation`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:usenix\s*)?symposium on networked systems design`,
			`(?i)usenix.*nsdi`,
			`(?i)^nsdi(?:\s*\d{2,4})?(?:\s*[\(\s].*\d{4})?`,
			`(?i)nsdi(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},
		"ISCA": {
			`(?i)international symposium on computer architecture`,
			`(?i)proceedings of the (?:\d+(?:st|nd|rd|th)?\s*)?(?:annual\s*)?international symposium on computer`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:acm/ieee\s*)?international symposium on computer architecture`,
			`(?i)^isca(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)isca\s+\d{4}`,
		},
		"PPoPP": {
			`(?i)symposium on principles and practice of parallel programming`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?symposium on principles and practice of parallel`,
			`(?i)principles and practice of parallel programming`,
			`(?i)^ppopp(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)ppopp\s+\d{4}`,
		},

		// ==================== HCI ====================
		"CHI": {
			`(?i)chi conference on human factors in computing systems`,
			`(?i)conference on human factors in computing systems.*chi`,
			`(?i)proceedings of the chi conference`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?chi conference`,
			`(?i)^chi(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},

		// ==================== Robotics ====================
		"ICRA": {
			`(?i)international conference on robotics and automation`,
			`(?i)ieee.*international conference on robotics and automation.*icra`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee\s*)?icra`,
			`(?i)^icra(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)icra\s+\d{4}`,
		},
		"IROS": {
			`(?i)international conference on intelligent robots and systems`,
			`(?i)ieee/rsj.*international conference on intelligent robots`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee/rsj\s*)?iros`,
			`(?i)^iros(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)iros\s+\d{4}`,
		},

		// ==================== Medical ====================
		"MICCAI": {
			`(?i)international conference on medical image computing and computer[- ]assisted`,
			`(?i)medical image computing and computer[- ]assisted intervention`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?miccai`,
			`(?i)^miccai(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)miccai\s+\d{4}`,
		},
		"MIDL": {
			`(?i)medical imaging with deep learning`,
			`(?i)^midl$`,
			`(?i)^midl\s+\d{4}$`,
		},
		"ISBI": {
			`(?i)international symposium on biomedical imaging`,
			`(?i)ieee.*international symposium on biomedical imaging`,
			`(?i)^isbi$`,
			`(?i)^isbi\s+\d{4}$`,
		},

		// ==================== Signal Processing ====================
		"ICASSP": {
			`(?i)international conference on acoustics, speech,? and signal processing`,
			`(?i)ieee.*international conference on acoustics.*icassp`,
			`(?i)icassp\s+\d{4}[\s\-]+\d{4}\s+ieee`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee\s*)?icassp`,
			`(?i)^icassp(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)icassp.*\d{4}.*acoustics`,
			`(?i)icassp['\"]?\d{2}`,
		},

		// ==================== Theory ====================
		"STOC": {
			`(?i)symposium on theory of computing`,
			`(?i)proceedings of the (?:\d+(?:st|nd|rd|th)?\s*)?(?:annual\s*)?acm symposium on theory of computing`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:acm\s*)?stoc`,
			`(?i)^stoc(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},
		"FOCS": {
			`(?i)foundations of computer science`,
			`(?i)ieee.*annual symposium on foundations of computer science.*focs`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee\s*)?symposium on foundations`,
			`(?i)^focs(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},
		"CRYPTO": {
			`(?i)annual international cryptology conference`,
			`(?i)cryptology\s+eprint\s+archive`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?crypto(?:logy)?(?:\s+conference)?`,
			`(?i)^crypto(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},
		"ASE": {
			`(?i)automated software engineering`,
			`(?i)ieee/acm.*international conference on automated software`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?(?:ieee/acm\s*)?ase`,
			`(?i)^ase(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},

		// ==================== CS Journals ====================
		"TPAMI": {
			`(?i)transactions on pattern analysis and machine intelligence`,
			`(?i)ieee tpami`,
			`(?i)^tpami$`,
		},
		"IJCV": {
			`(?i)international journal of computer vision`,
			`(?i)^ijcv$`,
		},
		"JMLR": {
			`(?i)journal of machine learning research`,
			`(?i)^jmlr$`,
		},
		"TACL": {
			`(?i)transactions of the association for computational linguistics`,
			`(?i)^tacl$`,
		},
		"TOG": {
			`(?i)transactions on graphics`,
			`(?i)acm tog`,
			`(?i)^tog$`,
		},

		// ==================== Top Journals ====================
		"Science": {
			`(?i)^science$`,
			`(?i)^science[\s,]+\d+\s*\(\d+\)`,
			`(?i)^science(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)science\s+\d+\s*\(\d+\).*\d{4}`,
		},
		"Nature": {
			`(?i)^nature$`,
			`(?i)^nature[\s,]+\d+\s*\(\d+\)`,
			`(?i)^nature(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)nature\s+\d+\s*\(\d+\).*\d{4}`,
		},
		"Cell": {
			`(?i)^cell$`,
			`(?i)^cell\s+\d{4}$`,
			`(?i)cell\s+\d+\s*\(\d+\)`,
		},

		// ==================== Medical Journals ====================
		"NEJM": {
			`(?i)new england journal of medicine`,
			`(?i)^nejm$`,
			`(?i)^nejm\s+\d{4}$`,
			`(?i)n\s*engl\s*j\s*med`,
		},
		"Lancet": {
			`(?i)^the\s+lancet$`,
			`(?i)^lancet$`,
			`(?i)^lancet\s+\d{4}$`,
		},
		"JAMA": {
			`(?i)journal of the american medical association`,
			`(?i)^jama$`,
			`(?i)^jama\s+\d{4}$`,
		},
		"Nature Medicine": {
			`(?i)nature medicine`,
			`(?i)^nat\s+med$`,
			`(?i)^nature\s+medicine$`,
			`(?i)nature\s+med(?:icine)?`,
		},
		"PNAS": {
			`(?i)proceedings of the national academy of sciences`,
			`(?i)^pnas$`,
			`(?i)^pnas\s+\d{4}$`,
			`(?i)proc\s+natl\s+acad\s+sci`,
		},
		"BMJ": {
			`(?i)british medical journal`,
			`(?i)^bmj$`,
			`(?i)^bmj\s+\d{4}$`,
		},

		// ==================== Nature子刊 ====================
		"Nature Genetics": {
			`(?i)nature genetics`,
			`(?i)^nat\s+genet$`,
			`(?i)^nature\s+genetics$`,
		},
		"Nature Biotechnology": {
			`(?i)nature biotechnology`,
			`(?i)^nat\s+biotechnol$`,
			`(?i)^nature\s+biotechnology$`,
		},
		"Nature Immunology": {
			`(?i)nature immunology`,
			`(?i)^nat\s+immunol$`,
			`(?i)^nature\s+immunology$`,
		},
		"Nature Methods": {
			`(?i)nature methods`,
			`(?i)^nat\s+methods$`,
			`(?i)^nature\s+methods$`,
		},
		"Nature Communications": {
			`(?i)nature communications`,
			`(?i)^nat\s+commun$`,
			`(?i)^nature\s+communications$`,
		},
		"Nature Biomedical Engineering": {
			`(?i)nature biomedical engineering`,
			`(?i)^nat\s+biomed\s+eng$`,
			`(?i)^nature\s+biomedical\s+engineering$`,
		},

		// ==================== 生物信息学 ====================
		"Bioinformatics": {
			`(?i)^bioinformatics$`,
			`(?i)^bioinformatics\s+\d{4}$`,
		},
		"Genome Research": {
			`(?i)genome research`,
			`(?i)^genome\s+res$`,
			`(?i)^genome\s+research$`,
		},
		"Genome Biology": {
			`(?i)genome biology`,
			`(?i)^genome\s+biol$`,
			`(?i)^genome\s+biology$`,
		},
		"Nucleic Acids Research": {
			`(?i)nucleic acids research`,
			`(?i)^nucleic\s+acids\s+res$`,
			`(?i)^nar$`,
		},
		"RECOMB": {
			`(?i)research in computational molecular biology`,
			`(?i)international conference on research in computational molecular biology`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?recomb`,
			`(?i)^recomb(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
		},
		"ISMB": {
			`(?i)intelligent systems for molecular biology`,
			`(?i)international conference on intelligent systems for molecular biology`,
			`(?i)\d+(?:st|nd|rd|th)?\s*(?:annual\s*)?ismb`,
			`(?i)^ismb(?:\s+\d{4})?(?:\s*,\s*[\d\-]+)?(?:\s*,\s*\d{4})?$`,
			`(?i)ismb['\"]?\d{2}`,
		},

		// ==================== 经济学顶刊 ====================
		"American Economic Review": {
			`(?i)american economic review`,
			`(?i)^aer$`,
			`(?i)^am\s+econ\s+rev$`,
		},
		"Quarterly Journal of Economics": {
			`(?i)quarterly journal of economics`,
			`(?i)^qje$`,
			`(?i)^q\s+j\s+econ$`,
		},
		"Journal of Political Economy": {
			`(?i)journal of political economy`,
			`(?i)^jpe$`,
			`(?i)^j\s+polit\s+econ$`,
		},
		"Econometrica": {
			`(?i)^econometrica$`,
			`(?i)^econometrica\s+\d{4}$`,
		},
		"Review of Economic Studies": {
			`(?i)review of economic studies`,
			`(?i)^restud$`,
			`(?i)^rev\s+econ\s+stud$`,
		},
		"Journal of Finance": {
			`(?i)journal of finance`,
			`(?i)^j\s+finance$`,
		},
		"Management Science": {
			`(?i)management science`,
			`(?i)^manag\s+sci$`,
		},
		"Operations Research": {
			`(?i)operations research`,
			`(?i)^oper\s+res$`,
		},

		// ==================== 其他 ====================
		"US Patent": {
			`(?i)us\s*patent\s*[\d,]+`,
			`(?i)u\.?s\.?\s*pat\.?\s*[\d,]+`,
			`(?i)united\s*states\s*patent\s*[\d,]+`,
			`(?i)patent\s*#?\s*[\d,]+`,
		},
		"arXiv": {
			`(?i)arxiv`,
		},
		"bioRxiv": {
			`(?i)^biorxiv$`,
			`(?i)^biorxiv\s+\d{4}$`,
			`(?i)biorxiv.*\d{4}`,
		},
		"eLife": {
			`(?i)^elife$`,
			`(?i)^elife\s+\d{4}$`,
		},
		"NBER Working Paper": {
			`(?i)nber working paper`,
			`(?i)national bureau of economic research.*working paper`,
			`(?i)^nber\s+wp$`,
			`(?i)nber.*working.*paper`,
		},
		"SSRN": {
			`(?i)social science research network`,
			`(?i)^ssrn$`,
			`(?i)ssrn.*\d{4}`,
		},
	}

	// 编译所有正则
	for name, patterns := range patternDefs {
		cm.patterns[name] = make([]*regexp.Regexp, 0, len(patterns))
		for _, p := range patterns {
			re, err := regexp.Compile(p)
			if err == nil {
				cm.patterns[name] = append(cm.patterns[name], re)
			}
		}
	}

	// 顶会/顶刊列表
	topTierList := []string{
		// AI & ML
		"NeurIPS", "ICML", "ICLR", "AAAI", "IJCAI", "AAMAS",
		// CV
		"CVPR", "ECCV", "ICCV", "SIGGRAPH", "SIGGRAPH Asia", "ACM MM", "3DV",
		// NLP
		"ACL", "ACL Findings", "EMNLP", "EMNLP Findings", "NAACL", "COLM", "ICASSP",
		// Web & IR
		"WWW", "SIGIR",
		// Data Mining
		"SIGMOD", "VLDB", "ICDE", "KDD",
		// Security
		"CCS", "USENIX Security", "S&P", "NDSS",
		// Systems
		"ISCA", "OSDI", "NSDI", "PPoPP",
		// HCI
		"CHI",
		// Theory
		"STOC", "FOCS", "CRYPTO",
		// SE
		"ASE",
		// Medical
		"MICCAI", "MIDL", "ISBI",
		// Robotics
		"ICRA", "IROS",
		// Top Journals
		"Nature", "Science", "Cell",
		"NEJM", "Lancet", "JAMA", "Nature Medicine", "PNAS", "BMJ",
		"Nature Genetics", "Nature Biotechnology", "Nature Immunology",
		"Nature Methods", "Nature Communications", "Nature Biomedical Engineering",
		"Bioinformatics", "Genome Research", "Genome Biology", "Nucleic Acids Research",
		"RECOMB", "ISMB", "eLife",
		// CS Journals
		"TPAMI", "IJCV", "JMLR", "TACL", "TOG",
		// Econ
		"American Economic Review", "Quarterly Journal of Economics",
		"Journal of Political Economy", "Econometrica", "Review of Economic Studies",
		"Journal of Finance", "Management Science", "Operations Research",
	}

	for _, name := range topTierList {
		cm.topTier[name] = true
	}
}

package fetcher

import (
	"encoding/csv"
	"os"
	"strings"
)

// RoleModelData CSV中的角色模型数据
type RoleModelData struct {
	Name         string
	Citation     string
	ScholarID    string
	PersonalPage string
	Twitter      string
	LinkedIn     string
	Image        string
	FamousWork   string
	Honor        string
	Institution  string
	Position     string
}

// RoleModelDB 角色模型数据库
type RoleModelDB struct {
	models []RoleModelData
}

// NewRoleModelDB 创建角色模型数据库
func NewRoleModelDB(csvPath string) (*RoleModelDB, error) {
	file, err := os.Open(csvPath)
	if err != nil {
		return &RoleModelDB{models: defaultRoleModels()}, nil
	}
	defer file.Close()

	reader := csv.NewReader(file)
	records, err := reader.ReadAll()
	if err != nil {
		return &RoleModelDB{models: defaultRoleModels()}, nil
	}

	var models []RoleModelData
	for i, record := range records {
		if i == 0 { // skip header
			continue
		}
		if len(record) < 11 {
			continue
		}
		models = append(models, RoleModelData{
			Name:         record[0],
			Citation:     record[1],
			ScholarID:    record[2],
			PersonalPage: record[3],
			Twitter:      record[4],
			LinkedIn:     record[5],
			Image:        record[6],
			FamousWork:   record[7],
			Honor:        record[8],
			Institution:  parseInstitution(record[9]),
			Position:     record[10],
		})
	}

	if len(models) == 0 {
		models = defaultRoleModels()
	}

	return &RoleModelDB{models: models}, nil
}

// parseInstitution 解析机构名（去掉logo URL）
func parseInstitution(s string) string {
	parts := strings.Split(s, ";")
	if len(parts) > 0 {
		return strings.TrimSpace(parts[0])
	}
	return s
}

// GetRoleModelList 获取角色模型名单（用于prompt）
func (db *RoleModelDB) GetRoleModelList() string {
	var names []string
	for _, m := range db.models {
		names = append(names, m.Name)
	}
	return strings.Join(names, ", ")
}

// FindByName 根据名字查找角色模型
func (db *RoleModelDB) FindByName(name string) *RoleModelData {
	nameLower := strings.ToLower(name)
	for i := range db.models {
		if strings.ToLower(db.models[i].Name) == nameLower {
			return &db.models[i]
		}
	}
	// 模糊匹配
	for i := range db.models {
		if strings.Contains(strings.ToLower(db.models[i].Name), nameLower) ||
			strings.Contains(nameLower, strings.ToLower(db.models[i].Name)) {
			return &db.models[i]
		}
	}
	return nil
}

// defaultRoleModels 默认角色模型列表
func defaultRoleModels() []RoleModelData {
	return []RoleModelData{
		{Name: "Geoffrey Hinton", Institution: "University of Toronto", Position: "Emeritus Professor", Image: "https://api.dinq.io/images/Geoffrey_Hinton.jpg", FamousWork: "Boltzmann machines, 1985"},
		{Name: "Yoshua Bengio", Institution: "University of Montreal", Position: "Professor", Image: "https://api.dinq.io/images/Yoshua_Bengio.jpg", FamousWork: "Generative Adversarial Net 2014"},
		{Name: "Yann LeCun", Institution: "Meta", Position: "Chief AI Scientist", Image: "https://api.dinq.io/images/Yann_LeCun.jpg", FamousWork: "LeNet 1998"},
		{Name: "Andrew Ng", Institution: "Stanford", Position: "Adjunct Professor", Image: "https://api.dinq.io/images/Andrew_Ng.jpg", FamousWork: "LDA 2003"},
		{Name: "Kaiming He", Institution: "MIT", Position: "Associate Professor", Image: "https://api.dinq.io/images/Kaiming_He.jpg", FamousWork: "ResNet 2016"},
		{Name: "Ian Goodfellow", Institution: "DeepMind", Position: "Research Scientist", Image: "https://api.dinq.io/images/Ian_Goodfellow.jpg", FamousWork: "Generative Adversarial Net 2014"},
		{Name: "Li Fei-Fei", Institution: "Stanford", Position: "Professor", Image: "https://api.dinq.io/images/Li_Fei-Fei.jpg", FamousWork: "ImageNet 2009"},
		{Name: "Jun-Yan Zhu", Institution: "CMU", Position: "Assistant Professor", Image: "https://api.dinq.io/images/Jun-Yan_Zhu.jpg", FamousWork: "CycleGAN 2017"},
		{Name: "Kyunghyun Cho", Institution: "New York University", Position: "Associate Professor", Image: "https://api.dinq.io/images/Kyunghyun_Cho.jpg", FamousWork: "CLIP 2021"},
		{Name: "Ashish Vaswani", Institution: "Essential AI", Position: "Co-founder and CEO", Image: "https://api.dinq.io/images/Ashish_Vaswani.png", FamousWork: "Attention is all you need 2017"},
	}
}
